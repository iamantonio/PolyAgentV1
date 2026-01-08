# Autonomous Polymarket Trader - Process Flow

```excalidraw-md
---
excalidraw-plugin: parsed
---

==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==

# Text Elements
START ^JKxRpqNm

Fetch Active Markets
(Gamma API: closed=false) ^r8TLCvNV

20 Active 2025 Markets ^VwmHXGbq

Select 10 Events
for Analysis ^zYnqMgNh

Map Events → Markets
(Gamma API) ^NhWLKjXt

84 Markets Found ^MtPcD4Ek

Loop Through Markets ^WvqQJYkz

Check: Is Crypto Market? ^aBcDeFgH

YES ^iJkLmNoP

NO ^qRsTuVwX

Fetch LunarCrush Data
- Galaxy Score
- AltRank
- Sentiment
- Social Volume ^yZaBcDeF

Grok Superforecaster Analysis
(with LunarCrush context if crypto) ^gHiJkLmN

Response: SKIP? ^oPqRsTuV

YES ^wXyZaBcD

NO ^eFgHiJkL

Parse Trade Output
- Price
- Size (%)
- Side (BUY/SELL) ^mNoPqRsT

Calculate USDC Amount
- Min: $1
- Max: $2 per trade ^uVwXyZaB

Safety Check
- Max $2 per position
- Max $10 total exposure ^cDeFgHiJ

PASS? ^kLmNoPqR

FAIL ^sTuVwXyZ

Execute Trade
(CLOB API) ^aBcDeFgH

Save Trade Record
/tmp/autonomous_trades.json ^iJkLmNoP

Skip Market
Try Next ^qRsTuVwX

Trade Complete! ^yZaBcDeF

Order ID
Transaction Hash ^gHiJkLmN

Grok AI
(xAI grok-4-1-fast-reasoning
2M context window) ^oPqRsTuV

LunarCrush API
(10 req/min)
5min cache ^wXyZaBcD

Polymarket
CLOB API ^eFgHiJkL

Safety Layer:
- $1 min order
- $2 max per trade
- $10 max total
- Manual exits only ^mNoPqRsT

Position Tracking:
status: "open"
Saved for manual close ^uVwXyZaB

# Element IDs and Coordinates
JKxRpqNm text 400 50 39 25 ^JKxRpqNm
r8TLCvNV text 350 120 210 50 ^r8TLCvNV
VwmHXGbq text 630 145 150 25 ^VwmHXGbq
zYnqMgNh text 360 220 180 50 ^zYnqMgNh
NhWLKjXt text 350 320 200 50 ^NhWLKjXt
MtPcD4Ek text 620 335 120 25 ^MtPcD4Ek
WvqQJYkz text 360 420 180 35 ^WvqQJYkz
aBcDeFgH rect 310 500 260 60 ^aBcDeFgH
iJkLmNoP text 420 560 40 25 ^iJkLmNoP
qRsTuVwX text 280 560 30 25 ^qRsTuVwX
yZaBcDeF rect 600 500 200 120 ^yZaBcDeF
gHiJkLmN rect 260 650 360 60 ^gHiJkLmN
oPqRsTuV diamond 380 750 120 80 ^oPqRsTuV
wXyZaBcD text 450 780 40 25 ^wXyZaBcD
eFgHiJkL text 280 780 30 25 ^eFgHiJkL
mNoPqRsT rect 260 880 360 100 ^mNoPqRsT
uVwXyZaB rect 260 1020 360 60 ^uVwXyZaB
cDeFgHiJ rect 260 1120 360 80 ^cDeFgHiJ
kLmNoPqR diamond 380 1240 120 80 ^kLmNoPqR
sTuVwXyZ text 280 1270 40 25 ^sTuVwXyZ
aBcDeFgH rect 440 1360 180 60 ^aBcDeFgH
iJkLmNoP rect 260 1480 360 60 ^iJkLmNoP
qRsTuVwX rect 120 880 100 80 ^qRsTuVwX
yZaBcDeF ellipse 450 1600 140 60 ^yZaBcDeF
gHiJkLmN text 250 1560 180 60 ^gHiJkLmN
oPqRsTuV rect 50 50 180 180 ^oPqRsTuV
wXyZaBcD rect 50 280 180 120 ^wXyZaBcD
eFgHiJkL rect 50 450 180 80 ^eFgHiJkL
mNoPqRsT rect 50 1100 180 140 ^mNoPqRsT
uVwXyZaB rect 50 1300 180 80 ^uVwXyZaB

# Drawing
```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin/releases/tag/2.0.0",
  "elements": [
    {
      "id": "JKxRpqNm",
      "type": "text",
      "x": 400,
      "y": 50,
      "width": 80,
      "height": 35,
      "angle": 0,
      "strokeColor": "#1e1e1e",
      "backgroundColor": "transparent",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "strokeStyle": "solid",
      "roughness": 1,
      "opacity": 100,
      "groupIds": [],
      "text": "START",
      "fontSize": 28,
      "fontFamily": 1,
      "textAlign": "center",
      "verticalAlign": "top",
      "baseline": 25
    },
    {
      "type": "rectangle",
      "x": 310,
      "y": 110,
      "width": 260,
      "height": 70,
      "strokeColor": "#2f9e44",
      "backgroundColor": "#d3f9d8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "fetchMarkets"
    },
    {
      "type": "text",
      "x": 320,
      "y": 120,
      "width": 240,
      "height": 50,
      "text": "Fetch Active Markets\n(Gamma API: closed=false)",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "r8TLCvNV"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 85,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow1"
    },
    {
      "type": "text",
      "x": 590,
      "y": 135,
      "width": 140,
      "height": 30,
      "text": "20 Active Markets",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "left",
      "strokeColor": "#2f9e44",
      "id": "marketsCount"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 180,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow2"
    },
    {
      "type": "rectangle",
      "x": 310,
      "y": 210,
      "width": 260,
      "height": 70,
      "strokeColor": "#2f9e44",
      "backgroundColor": "#d3f9d8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "selectEvents"
    },
    {
      "type": "text",
      "x": 320,
      "y": 225,
      "width": 240,
      "height": 40,
      "text": "Select 10 Events\nfor Analysis",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "zYnqMgNh"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 280,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow3"
    },
    {
      "type": "rectangle",
      "x": 310,
      "y": 310,
      "width": 260,
      "height": 70,
      "strokeColor": "#2f9e44",
      "backgroundColor": "#d3f9d8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "mapMarkets"
    },
    {
      "type": "text",
      "x": 320,
      "y": 320,
      "width": 240,
      "height": 50,
      "text": "Map Events → Markets\n(Gamma API)",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "NhWLKjXt"
    },
    {
      "type": "text",
      "x": 590,
      "y": 335,
      "width": 120,
      "height": 25,
      "text": "84 Markets",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "left",
      "strokeColor": "#2f9e44",
      "id": "MtPcD4Ek"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 380,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow4"
    },
    {
      "type": "rectangle",
      "x": 310,
      "y": 410,
      "width": 260,
      "height": 60,
      "strokeColor": "#f08c00",
      "backgroundColor": "#fff4e6",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "loopMarkets"
    },
    {
      "type": "text",
      "x": 320,
      "y": 425,
      "width": 240,
      "height": 30,
      "text": "Loop Through Markets",
      "fontSize": 18,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "WvqQJYkz"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 470,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow5"
    },
    {
      "type": "diamond",
      "x": 350,
      "y": 500,
      "width": 180,
      "height": 80,
      "strokeColor": "#e03131",
      "backgroundColor": "#ffe8e8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "cryptoCheck"
    },
    {
      "type": "text",
      "x": 360,
      "y": 525,
      "width": 160,
      "height": 30,
      "text": "Is Crypto Market?",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "aBcDeFgH"
    },
    {
      "type": "arrow",
      "x": 530,
      "y": 540,
      "width": 60,
      "height": 0,
      "strokeColor": "#2f9e44",
      "endArrowhead": "arrow",
      "id": "arrowYes"
    },
    {
      "type": "text",
      "x": 540,
      "y": 520,
      "width": 40,
      "height": 25,
      "text": "YES",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "strokeColor": "#2f9e44",
      "id": "iJkLmNoP"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 580,
      "width": 0,
      "height": 30,
      "strokeColor": "#e03131",
      "endArrowhead": "arrow",
      "id": "arrowNo"
    },
    {
      "type": "text",
      "x": 450,
      "y": 590,
      "width": 30,
      "height": 25,
      "text": "NO",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "strokeColor": "#e03131",
      "id": "qRsTuVwX"
    },
    {
      "type": "rectangle",
      "x": 600,
      "y": 500,
      "width": 220,
      "height": 120,
      "strokeColor": "#9c36b5",
      "backgroundColor": "#f3d9fa",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "lunarcrush"
    },
    {
      "type": "text",
      "x": 610,
      "y": 510,
      "width": 200,
      "height": 100,
      "text": "Fetch LunarCrush\n- Galaxy Score\n- AltRank\n- Sentiment\n- Social Volume",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "left",
      "id": "yZaBcDeF"
    },
    {
      "type": "arrow",
      "x": 710,
      "y": 620,
      "width": 0,
      "height": 20,
      "strokeColor": "#9c36b5",
      "endArrowhead": "arrow",
      "id": "arrowLunar"
    },
    {
      "type": "arrow",
      "x": 710,
      "y": 640,
      "width": 100,
      "height": 40,
      "strokeColor": "#9c36b5",
      "endArrowhead": "arrow",
      "id": "arrowMerge"
    },
    {
      "type": "rectangle",
      "x": 260,
      "y": 650,
      "width": 360,
      "height": 70,
      "strokeColor": "#1971c2",
      "backgroundColor": "#d0ebff",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "grokAnalysis"
    },
    {
      "type": "text",
      "x": 270,
      "y": 660,
      "width": 340,
      "height": 50,
      "text": "Grok Superforecaster Analysis\n(w/ LunarCrush if crypto)",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "gHiJkLmN"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 720,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow6"
    },
    {
      "type": "diamond",
      "x": 360,
      "y": 750,
      "width": 160,
      "height": 80,
      "strokeColor": "#e03131",
      "backgroundColor": "#ffe8e8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "skipCheck"
    },
    {
      "type": "text",
      "x": 370,
      "y": 775,
      "width": 140,
      "height": 30,
      "text": "SKIP?",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "oPqRsTuV"
    },
    {
      "type": "arrow",
      "x": 360,
      "y": 790,
      "width": -140,
      "height": 100,
      "strokeColor": "#e03131",
      "endArrowhead": "arrow",
      "id": "arrowSkipYes"
    },
    {
      "type": "text",
      "x": 310,
      "y": 800,
      "width": 40,
      "height": 25,
      "text": "YES",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "strokeColor": "#e03131",
      "id": "wXyZaBcD"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 830,
      "width": 0,
      "height": 30,
      "strokeColor": "#2f9e44",
      "endArrowhead": "arrow",
      "id": "arrowSkipNo"
    },
    {
      "type": "text",
      "x": 450,
      "y": 840,
      "width": 30,
      "height": 25,
      "text": "NO",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "strokeColor": "#2f9e44",
      "id": "eFgHiJkL"
    },
    {
      "type": "rectangle",
      "x": 120,
      "y": 900,
      "width": 120,
      "height": 60,
      "strokeColor": "#868e96",
      "backgroundColor": "#f1f3f5",
      "fillStyle": "solid",
      "strokeWidth": 1,
      "roughness": 1,
      "id": "skipMarket"
    },
    {
      "type": "text",
      "x": 130,
      "y": 915,
      "width": 100,
      "height": 30,
      "text": "Skip Market\nTry Next",
      "fontSize": 12,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "qRsTuVwX"
    },
    {
      "type": "arrow",
      "x": 180,
      "y": 900,
      "width": 0,
      "height": -450,
      "strokeColor": "#868e96",
      "endArrowhead": "arrow",
      "strokeStyle": "dashed",
      "id": "arrowLoop"
    },
    {
      "type": "rectangle",
      "x": 260,
      "y": 870,
      "width": 360,
      "height": 80,
      "strokeColor": "#1971c2",
      "backgroundColor": "#d0ebff",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "parseTrade"
    },
    {
      "type": "text",
      "x": 270,
      "y": 880,
      "width": 340,
      "height": 60,
      "text": "Parse Trade Output\n- Price  - Size (%)  - Side",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "mNoPqRsT"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 950,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow7"
    },
    {
      "type": "rectangle",
      "x": 260,
      "y": 980,
      "width": 360,
      "height": 70,
      "strokeColor": "#1971c2",
      "backgroundColor": "#d0ebff",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "calcAmount"
    },
    {
      "type": "text",
      "x": 270,
      "y": 995,
      "width": 340,
      "height": 40,
      "text": "Calculate USDC Amount\nMin: $1  Max: $2",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "uVwXyZaB"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 1050,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow8"
    },
    {
      "type": "rectangle",
      "x": 260,
      "y": 1080,
      "width": 360,
      "height": 80,
      "strokeColor": "#f08c00",
      "backgroundColor": "#fff4e6",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "safetyCheck"
    },
    {
      "type": "text",
      "x": 270,
      "y": 1090,
      "width": 340,
      "height": 60,
      "text": "Safety Check\n$2 per trade / $10 total",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "cDeFgHiJ"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 1160,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow9"
    },
    {
      "type": "diamond",
      "x": 360,
      "y": 1190,
      "width": 160,
      "height": 80,
      "strokeColor": "#e03131",
      "backgroundColor": "#ffe8e8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "passCheck"
    },
    {
      "type": "text",
      "x": 370,
      "y": 1215,
      "width": 140,
      "height": 30,
      "text": "PASS?",
      "fontSize": 16,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "kLmNoPqR"
    },
    {
      "type": "arrow",
      "x": 360,
      "y": 1230,
      "width": -110,
      "height": 0,
      "strokeColor": "#e03131",
      "endArrowhead": "arrow",
      "id": "arrowFail"
    },
    {
      "type": "text",
      "x": 310,
      "y": 1210,
      "width": 40,
      "height": 25,
      "text": "FAIL",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "strokeColor": "#e03131",
      "id": "sTuVwXyZ"
    },
    {
      "type": "arrow",
      "x": 250,
      "y": 1230,
      "width": -50,
      "height": -280,
      "strokeColor": "#e03131",
      "strokeStyle": "dashed",
      "endArrowhead": "arrow",
      "id": "arrowReject"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 1270,
      "width": 0,
      "height": 30,
      "strokeColor": "#2f9e44",
      "endArrowhead": "arrow",
      "id": "arrowPass"
    },
    {
      "type": "rectangle",
      "x": 340,
      "y": 1310,
      "width": 200,
      "height": 60,
      "strokeColor": "#2f9e44",
      "backgroundColor": "#d3f9d8",
      "fillStyle": "solid",
      "strokeWidth": 3,
      "roughness": 1,
      "id": "execute"
    },
    {
      "type": "text",
      "x": 350,
      "y": 1325,
      "width": 180,
      "height": 30,
      "text": "Execute Trade",
      "fontSize": 20,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "aBcDeFgH"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 1370,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow10"
    },
    {
      "type": "rectangle",
      "x": 260,
      "y": 1400,
      "width": 360,
      "height": 60,
      "strokeColor": "#2f9e44",
      "backgroundColor": "#d3f9d8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 1,
      "id": "saveTrade"
    },
    {
      "type": "text",
      "x": 270,
      "y": 1412,
      "width": 340,
      "height": 36,
      "text": "Save Trade Record\nautonomous_trades.json",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "iJkLmNoP"
    },
    {
      "type": "arrow",
      "x": 440,
      "y": 1460,
      "width": 0,
      "height": 20,
      "strokeColor": "#1e1e1e",
      "endArrowhead": "arrow",
      "id": "arrow11"
    },
    {
      "type": "ellipse",
      "x": 360,
      "y": 1490,
      "width": 160,
      "height": 70,
      "strokeColor": "#2f9e44",
      "backgroundColor": "#d3f9d8",
      "fillStyle": "solid",
      "strokeWidth": 3,
      "roughness": 1,
      "id": "complete"
    },
    {
      "type": "text",
      "x": 375,
      "y": 1510,
      "width": 130,
      "height": 30,
      "text": "✅ COMPLETE",
      "fontSize": 18,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "yZaBcDeF"
    },
    {
      "type": "text",
      "x": 250,
      "y": 1480,
      "width": 100,
      "height": 50,
      "text": "Order ID\nTx Hash",
      "fontSize": 12,
      "fontFamily": 1,
      "textAlign": "left",
      "strokeColor": "#2f9e44",
      "id": "gHiJkLmN"
    },
    {
      "type": "rectangle",
      "x": 50,
      "y": 50,
      "width": 180,
      "height": 130,
      "strokeColor": "#1971c2",
      "backgroundColor": "#e7f5ff",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 0,
      "id": "grokBox"
    },
    {
      "type": "text",
      "x": 60,
      "y": 60,
      "width": 160,
      "height": 110,
      "text": "🤖 Grok AI\nxAI\ngrok-4-1-fast-\nreasoning\n2M context",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "oPqRsTuV"
    },
    {
      "type": "rectangle",
      "x": 50,
      "y": 220,
      "width": 180,
      "height": 100,
      "strokeColor": "#9c36b5",
      "backgroundColor": "#f3d9fa",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 0,
      "id": "lunarBox"
    },
    {
      "type": "text",
      "x": 60,
      "y": 235,
      "width": 160,
      "height": 70,
      "text": "🌙 LunarCrush\n10 req/min\n5min cache",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "wXyZaBcD"
    },
    {
      "type": "rectangle",
      "x": 50,
      "y": 360,
      "width": 180,
      "height": 70,
      "strokeColor": "#2f9e44",
      "backgroundColor": "#d3f9d8",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 0,
      "id": "clobBox"
    },
    {
      "type": "text",
      "x": 60,
      "y": 375,
      "width": 160,
      "height": 40,
      "text": "📊 Polymarket\nCLOB API",
      "fontSize": 14,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "eFgHiJkL"
    },
    {
      "type": "rectangle",
      "x": 50,
      "y": 1000,
      "width": 180,
      "height": 130,
      "strokeColor": "#f08c00",
      "backgroundColor": "#fff4e6",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 0,
      "id": "safetyBox"
    },
    {
      "type": "text",
      "x": 60,
      "y": 1015,
      "width": 160,
      "height": 100,
      "text": "🛡️ Safety:\n$1 min\n$2 max/trade\n$10 max total\nManual exits",
      "fontSize": 13,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "mNoPqRsT"
    },
    {
      "type": "rectangle",
      "x": 50,
      "y": 1170,
      "width": 180,
      "height": 70,
      "strokeColor": "#1971c2",
      "backgroundColor": "#d0ebff",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roughness": 0,
      "id": "trackBox"
    },
    {
      "type": "text",
      "x": 60,
      "y": 1185,
      "width": 160,
      "height": 40,
      "text": "📝 Position:\nstatus: \"open\"",
      "fontSize": 13,
      "fontFamily": 1,
      "textAlign": "center",
      "id": "uVwXyZaB"
    }
  ]
}
```

---

## Key Components

### 1. **Market Discovery (Green)**
- Fetches 20 active 2025 markets from Gamma API
- Filters for unclosed markets only
- Maps events to individual tradeable markets

### 2. **LunarCrush Integration (Purple)** 🌙
- Detects crypto markets automatically
- Fetches social intelligence data
- 10 req/min rate limit with 5min cache
- Galaxy Score, AltRank, Sentiment, Social Volume

### 3. **Grok AI Analysis (Blue)** 🤖
- xAI grok-4-1-fast-reasoning
- 2M context window
- Superforecaster methodology
- Enhanced with LunarCrush for crypto

### 4. **Safety Layer (Orange)** 🛡️
- Minimum $1 order size
- Maximum $2 per trade
- Maximum $10 total exposure
- Manual exits only (API limitation)

### 5. **Execution (Green)** ✅
- Direct CLOB API orders
- FOK (Fill-Or-Kill) orders
- Saved to JSON with full tracking
- Order ID + Transaction Hash

### 6. **Position Tracking (Blue)** 📝
- All trades saved to /tmp/autonomous_trades.json
- Status: "open" for manual closing
- Full execution details preserved

---

## Current Performance

**First Successful Trade:**
- Market: "Tim Cook out as Apple CEO in 2025?"
- Analysis: Grok predicted 1% chance (vs 0.25% market price)
- Execution: Bought 241.596 shares @ $1 USDC
- Status: OPEN (manual exit required)

**Balance:**
- Started: 49.41 USDC
- Current: 48.41 USDC available
- Exposure: 1.00 USDC (1 open position)
- Capacity: 9.00 USDC remaining
