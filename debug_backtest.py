#!/usr/bin/env python3
import pandas as pd

df = pd.read_parquet("data/backtest/synthetic_historical_data.parquet")

print("Checking mean-reversion strategy conditions:")
print(f"Total snapshots: {len(df)}")

df['deviation'] = abs(df['mid_price'] - 0.5)
print(f"\nSnapshots with deviation > 0.2: {(df['deviation'] > 0.2).sum()}")
print(f"Snapshots with deviation > 0.15: {(df['deviation'] > 0.15).sum()}")
print(f"Snapshots with deviation > 0.1: {(df['deviation'] > 0.1).sum()}")

print("\nPrice distribution:")
print(df['mid_price'].describe())

print("\nSample data with high deviation:")
high_dev = df[df['deviation'] > 0.15][['timestamp', 'question', 'mid_price', 'deviation', 'liquidity']].head(10)
print(high_dev)

print("\nChecking unique markets:")
print(f"Unique market slugs: {df['market_slug'].nunique()}")
print(df['market_slug'].unique()[:5])
