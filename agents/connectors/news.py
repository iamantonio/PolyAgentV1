from datetime import datetime
import os

from newsapi import NewsApiClient

from agents.utils.objects import Article


class News:
    def __init__(self) -> None:
        self.configs = {
            "language": "en",
            "country": "us",
            "top_headlines": "https://newsapi.org/v2/top-headlines?country=us&apiKey=",
            "base_url": "https://newsapi.org/v2/",
        }

        self.categories = {
            "business",
            "entertainment",
            "general",
            "health",
            "science",
            "sports",
            "technology",
        }

        self.API = NewsApiClient(os.getenv("NEWSAPI_API_KEY"))

    def get_articles_for_cli_keywords(self, keywords) -> "list[Article]":
        query_words = keywords.split(",")
        all_articles = self.get_articles_for_options(query_words)
        article_objects: list[Article] = []
        for _, articles in all_articles.items():
            for article in articles:
                article_objects.append(Article(**article))
        return article_objects

    def get_top_articles_for_market(self, market_object: dict) -> "list[Article]":
        import time
        from agents.utils.validation_logger import validation_logger

        start_time = time.time()
        try:
            result = self.API.get_top_headlines(
                language="en", country="usa", q=market_object["description"]
            )
            duration_ms = (time.time() - start_time) * 1000
            validation_logger.log_api_call("news_get_top_headlines", success=True, duration_ms=duration_ms)
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            validation_logger.log_api_call("news_get_top_headlines", success=False,
                                          error_msg=str(e), duration_ms=duration_ms)
            raise

    def get_articles_for_options(
        self,
        market_options: "list[str]",
        date_start: datetime = None,
        date_end: datetime = None,
    ) -> "list[Article]":
        import time
        from agents.utils.validation_logger import validation_logger

        all_articles = {}
        # Default to top articles if no start and end dates are given for search
        if not date_start and not date_end:
            for option in market_options:
                start_time = time.time()
                try:
                    response_dict = self.API.get_top_headlines(
                        q=option.strip(),
                        language=self.configs["language"],
                        country=self.configs["country"],
                    )
                    duration_ms = (time.time() - start_time) * 1000
                    validation_logger.log_api_call("news_get_headlines_for_option", success=True, duration_ms=duration_ms)
                    articles = response_dict["articles"]
                    all_articles[option] = articles
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    validation_logger.log_api_call("news_get_headlines_for_option", success=False,
                                                  error_msg=str(e), duration_ms=duration_ms)
                    # Continue with other options even if one fails
                    print(f"Failed to get news for {option}: {e}")
        else:
            for option in market_options:
                start_time = time.time()
                try:
                    response_dict = self.API.get_everything(
                        q=option.strip(),
                        language=self.configs["language"],
                        country=self.configs["country"],
                        from_param=date_start,
                        to=date_end,
                    )
                    duration_ms = (time.time() - start_time) * 1000
                    validation_logger.log_api_call("news_get_everything_for_option", success=True, duration_ms=duration_ms)
                    articles = response_dict["articles"]
                    all_articles[option] = articles
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    validation_logger.log_api_call("news_get_everything_for_option", success=False,
                                                  error_msg=str(e), duration_ms=duration_ms)
                    # Continue with other options even if one fails
                    print(f"Failed to get news for {option}: {e}")

        return all_articles

    def get_category(self, market_object: dict) -> str:
        news_category = "general"
        market_category = market_object["category"]
        if market_category in self.categories:
            news_category = market_category
        return news_category
