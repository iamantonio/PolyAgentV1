import os
import json
import ast
import re
from typing import List, Dict, Any

import math

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.connectors.chroma import PolymarketRAG as Chroma
from agents.utils.objects import SimpleEvent, SimpleMarket
from agents.application.prompts import Prompter
from agents.polymarket.polymarket import Polymarket
from agents.application.budget_enforcer import BudgetEnforcer

def retain_keys(data, keys_to_retain):
    if isinstance(data, dict):
        return {
            key: retain_keys(value, keys_to_retain)
            for key, value in data.items()
            if key in keys_to_retain
        }
    elif isinstance(data, list):
        return [retain_keys(item, keys_to_retain) for item in data]
    else:
        return data

class Executor:
    def __init__(self, default_model='grok-4-1-fast-reasoning', use_grok=True) -> None:
        load_dotenv()

        # Model token limits
        max_token_model = {
            'grok-4-1-fast-reasoning': 2000000,  # 2M tokens!
            'grok-4-1-fast-non-reasoning': 2000000,
            'gpt-3.5-turbo-16k': 15000,
            'gpt-4-1106-preview': 95000
        }

        self.token_limit = max_token_model.get(default_model, 100000)
        self.prompter = Prompter()

        # Configure for Grok or OpenAI
        if use_grok:
            xai_api_key = os.getenv("XAI_API_KEY")
            if not xai_api_key:
                raise ValueError("XAI_API_KEY not found in .env - add it to use Grok")

            self.llm = ChatOpenAI(
                model=default_model,
                temperature=0,
                api_key=xai_api_key,
                base_url="https://api.x.ai/v1"
            )
        else:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
            self.llm = ChatOpenAI(
                model=default_model,
                temperature=0,
            )

        self.gamma = Gamma()
        self.chroma = Chroma()
        self.polymarket = Polymarket()
        self.budget = BudgetEnforcer()

    def _safe_llm_call(self, messages: list, market_id: Optional[str] = None) -> Optional[str]:
        """
        Safely call LLM with budget enforcement.

        Returns:
            LLM response content, or None if blocked by budget
        """
        # Check budget before call
        allowed, reason = self.budget.can_call_llm(market_id)
        if not allowed:
            print(f"⛔ [BUDGET] LLM call blocked: {reason}")
            stats = self.budget.get_stats()
            print(f"   Daily: ${stats['daily_spend']:.2f}/${stats['daily_budget']:.2f} | " +
                  f"Hourly: ${stats['hourly_spend']:.2f}/${stats['hourly_budget']:.2f} | " +
                  f"Calls: {stats['calls_this_hour']}/{stats['max_calls_per_hour']}")
            return None

        # Make the call
        result = self.llm.invoke(messages)

        # Estimate cost (rough approximation)
        # TODO: Extract actual tokens from response metadata
        estimated_tokens = len(str(messages)) // 4 + len(result.content) // 4
        # Grok pricing is different from OpenAI, using conservative estimate
        estimated_cost = Decimal(str(estimated_tokens * 0.00002))  # ~$0.02 per 1K tokens

        # Record the call
        self.budget.record_call(estimated_cost, market_id)

        return result.content

    def get_llm_response(self, user_input: str) -> Optional[str]:
        system_message = SystemMessage(content=str(self.prompter.market_analyst()))
        human_message = HumanMessage(content=user_input)
        messages = [system_message, human_message]
        return self._safe_llm_call(messages)

    def get_superforecast(
        self, event_title: str, market_question: str, outcome: str
    ) -> Optional[str]:
        messages = self.prompter.superforecaster(
            description=event_title, question=market_question, outcome=outcome
        )
        return self._safe_llm_call(messages)


    def estimate_tokens(self, text: str) -> int:
        # This is a rough estimate. For more accurate results, consider using a tokenizer.
        return len(text) // 4  # Assuming average of 4 characters per token

    def process_data_chunk(self, data1: List[Dict[Any, Any]], data2: List[Dict[Any, Any]], user_input: str) -> str:
        system_message = SystemMessage(
            content=str(self.prompter.prompts_polymarket(data1=data1, data2=data2))
        )
        human_message = HumanMessage(content=user_input)
        messages = [system_message, human_message]
        result = self.llm.invoke(messages)
        return result.content


    def divide_list(self, original_list, i):
        # Calculate the size of each sublist
        sublist_size = math.ceil(len(original_list) / i)
        
        # Use list comprehension to create sublists
        return [original_list[j:j+sublist_size] for j in range(0, len(original_list), sublist_size)]
    
    def get_polymarket_llm(self, user_input: str) -> str:
        data1 = self.gamma.get_current_events()
        data2 = self.gamma.get_current_markets()
        
        combined_data = str(self.prompter.prompts_polymarket(data1=data1, data2=data2))
        
        # Estimate total tokens
        total_tokens = self.estimate_tokens(combined_data)
        
        # Set a token limit (adjust as needed, leaving room for system and user messages)
        token_limit = self.token_limit
        if total_tokens <= token_limit:
            # If within limit, process normally
            return self.process_data_chunk(data1, data2, user_input)
        else:
            # If exceeding limit, process in chunks
            chunk_size = len(combined_data) // ((total_tokens // token_limit) + 1)
            print(f'total tokens {total_tokens} exceeding llm capacity, now will split and answer')
            group_size = (total_tokens // token_limit) + 1 # 3 is safe factor
            keys_no_meaning = ['image','pagerDutyNotificationEnabled','resolvedBy','endDate','clobTokenIds','negRiskMarketID','conditionId','updatedAt','startDate']
            useful_keys = ['id','questionID','description','liquidity','clobTokenIds','outcomes','outcomePrices','volume','startDate','endDate','question','questionID','events']
            data1 = retain_keys(data1, useful_keys)
            cut_1 = self.divide_list(data1, group_size)
            cut_2 = self.divide_list(data2, group_size)
            cut_data_12 = zip(cut_1, cut_2)

            results = []

            for cut_data in cut_data_12:
                sub_data1 = cut_data[0]
                sub_data2 = cut_data[1]
                sub_tokens = self.estimate_tokens(str(self.prompter.prompts_polymarket(data1=sub_data1, data2=sub_data2)))

                result = self.process_data_chunk(sub_data1, sub_data2, user_input)
                results.append(result)
            
            combined_result = " ".join(results)
            
        
            
            return combined_result
    def filter_events(self, events: "list[SimpleEvent]") -> str:
        prompt = self.prompter.filter_events(events)
        result = self.llm.invoke(prompt)
        return result.content

    def filter_events_with_rag(self, events: "list[SimpleEvent]") -> str:
        prompt = self.prompter.filter_events()
        print()
        print("... prompting ... ", prompt)
        print()
        return self.chroma.events(events, prompt)

    def map_filtered_events_to_markets(
        self, filtered_events: "list[SimpleEvent]"
    ) -> "list[SimpleMarket]":
        markets = []
        for e in filtered_events:
            data = json.loads(e[0].json())
            market_ids = data["metadata"]["markets"].split(",")
            for market_id in market_ids:
                market_data = self.gamma.get_market(market_id)
                formatted_market_data = self.polymarket.map_api_to_market(market_data)
                markets.append(formatted_market_data)
        return markets

    def filter_markets(self, markets) -> "list[tuple]":
        prompt = self.prompter.filter_markets()
        print()
        print("... prompting ... ", prompt)
        print()
        return self.chroma.markets(markets, prompt)

    def source_best_trade_unified(self, market_object, lunarcrush_context: str = None) -> Optional[str]:
        """
        Unified single-LLM-call version of source_best_trade.
        50% cost savings by combining analysis + trade decision into ONE call.
        """
        market_document = market_object[0].dict()
        market = market_document["metadata"]
        outcome_prices = ast.literal_eval(market["outcome_prices"])
        outcomes = ast.literal_eval(market["outcomes"])
        question = market["question"]
        description = market_document["page_content"]
        market_id = market.get("condition_id", "unknown")

        # SINGLE LLM CALL: Combined analysis + trade decision
        prompt = self.prompter.unified_trade_decision(
            question, description, outcomes, str(outcome_prices), lunarcrush_context
        )
        print()
        print("... unified prompting ... ", prompt[:200], "...")
        print()
        content = self._safe_llm_call([HumanMessage(content=prompt)], market_id)

        # If budget blocked, return HOLD signal
        if content is None:
            print("⛔ [BUDGET] Returning HOLD - budget exhausted")
            return "SKIP: Budget exhausted"

        print("result: ", content)
        print()

        # Check if the market is resolved/skipped
        if "SKIP:" in content:
            return content

        # Parse JSON response
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            trade_data = json.loads(json_str)

            # Convert to legacy format for compatibility
            outcome = trade_data["recommended_outcome"]
            price = trade_data["max_entry_price"]
            size = trade_data["position_size_pct"]

            return f"outcome:'{outcome}',price:{price},size:{size},"

        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️ Failed to parse unified response: {e}")
            print(f"Raw content: {content}")
            return "SKIP: Failed to parse LLM response"

    def source_best_trade(self, market_object, lunarcrush_context: str = None) -> Optional[str]:
        market_document = market_object[0].dict()
        market = market_document["metadata"]
        outcome_prices = ast.literal_eval(market["outcome_prices"])
        outcomes = ast.literal_eval(market["outcomes"])
        question = market["question"]
        description = market_document["page_content"]
        market_id = market.get("condition_id", "unknown")  # Extract market ID for budget tracking

        # FIRST LLM CALL: Superforecaster analysis
        prompt = self.prompter.superforecaster(question, description, outcomes, lunarcrush_context)
        print()
        print("... prompting ... ", prompt)
        print()
        content = self._safe_llm_call(prompt, market_id)

        # If budget blocked, return HOLD signal
        if content is None:
            print("⛔ [BUDGET] Returning HOLD - budget exhausted")
            return "SKIP: Budget exhausted"

        print("result: ", content)
        print()

        # Check if the market is resolved/skipped
        if "SKIP:" in content:
            return content  # Return the SKIP message directly

        # SECOND LLM CALL: Trade calculation
        prompt = self.prompter.one_best_trade(content, outcomes, outcome_prices)
        print("... prompting ... ", prompt)
        print()
        content = self._safe_llm_call(prompt, market_id)

        # If budget blocked on second call, return HOLD
        if content is None:
            print("⛔ [BUDGET] Returning HOLD - budget exhausted")
            return "SKIP: Budget exhausted"

        print("result: ", content)
        print()
        return content

    def format_trade_prompt_for_execution(self, best_trade: str) -> float:
        data = best_trade.split(",")
        # price = re.findall("\d+\.\d+", data[0])[0]
        size = re.findall("\d+\.\d+", data[1])[0]
        usdc_balance = self.polymarket.get_usdc_balance()
        return float(size) * usdc_balance

    def source_best_market_to_create(self, filtered_markets) -> str:
        prompt = self.prompter.create_new_market(filtered_markets)
        print()
        print("... prompting ... ", prompt)
        print()
        result = self.llm.invoke(prompt)
        content = result.content
        return content
