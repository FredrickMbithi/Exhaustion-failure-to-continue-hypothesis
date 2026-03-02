"""
Generate comprehensive final report for exhaustion-failure strategy.

Combines:
1. Cross-pair validation results
2. Full backtest performance
3. Statistical significance tests
4. Risk metrics and trade analysis
5. Deployment recommendations
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np


def generate_final_report(
    cross_pair_results: pd.DataFrame,
    backtest_summary: pd.DataFrame,
    trades_dir: Path,
    output_path: Path
):
    """Generate markdown report with all findings."""
    
    report = []
    report.append("# Exhaustion-Failure-to-Continue Strategy")
    report.append("## Final Results Report")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("\n---\n")
    
    # Executive Summary
    report.append("## Executive Summary\n")
    
    # Overall performance
    total_trades = backtest_summary['Trades'].astype(str).str.replace(',', '').astype(int).sum()
    avg_win_rate = cross_pair_results['win_rate'].mean()
    significant_pairs = (cross_pair_results['ic_pvalue'] < 0.05).sum()
    total_pairs = len(cross_pair_results)
    
    report.append(f"**Strategy:** Mean reversion based on exhaustion-failure-to-continue pattern\n")
    report.append(f"**Test Period:** 2023-2025 (hourly FX data)\n")
    report.append(f"**Pairs Tested:** {total_pairs}\n")
    report.append(f"**Total Trades:** {total_trades}\n")
    report.append(f"**Average Win Rate:** {avg_win_rate:.1%}\n")
    report.append(f"**Statistically Significant Pairs:** {significant_pairs}/{total_pairs} ({significant_pairs/total_pairs:.0%})\n")
    
    # Key findings
    report.append("\n### Key Findings\n")
    
    if avg_win_rate >= 0.60:
        report.append(f"✅ **STRONG PERFORMANCE:** Average win rate of {avg_win_rate:.1%} exceeds 60% target\n")
    elif avg_win_rate >= 0.55:
        report.append(f"⚠️ **MODERATE PERFORMANCE:** Average win rate of {avg_win_rate:.1%} meets baseline expectations\n")
    else:
        report.append(f"❌ **WEAK PERFORMANCE:** Average win rate of {avg_win_rate:.1%} below 55% threshold\n")
    
    if significant_pairs / total_pairs >= 0.5:
        report.append(f"✅ **STATISTICAL SIGNIFICANCE:** {significant_pairs/total_pairs:.0%} of pairs show significant IC (p < 0.05)\n")
    else:
        report.append(f"❌ **LIMITED SIGNIFICANCE:** Only {significant_pairs/total_pairs:.0%} of pairs show significant IC\n")
    
    # Cross-pair consistency
    ic_positive = (cross_pair_results['ic'] > 0).sum()
    ic_consistency = ic_positive / len(cross_pair_results)
    
    if ic_consistency >= 0.7:
        report.append(f"✅ **CROSS-PAIR CONSISTENCY:** {ic_consistency:.0%} of pairs have positive IC\n")
    else:
        report.append(f"⚠️ **INCONSISTENT SIGNALS:** Only {ic_consistency:.0%} of pairs have positive IC\n")
    
    report.append("\n---\n")
    
    # Cross-Pair Validation Results
    report.append("## 1. Cross-Pair Validation\n")
    report.append("### Signal Generation Statistics\n")
    
    report.append("| Pair | Signals | IC | t-stat | p-value | Win Rate | Sharpe |\n")
    report.append("|------|---------|----|---------|---------|-----------|---------|\n")
    
    for _, row in cross_pair_results.iterrows():
        sig_marker = "✓" if row['ic_pvalue'] < 0.05 else " "
        report.append(
            f"| {sig_marker} {row['pair']} | {row['n_signals']:.0f} | "
            f"{row['ic']:.3f} | {row['ic_tstat_hac']:.2f} | "
            f"{row['ic_pvalue']:.4f} | {row['win_rate']:.1%} | "
            f"{row['sharpe']:.2f} |\n"
        )
    
    report.append(f"\n**Mean IC:** {cross_pair_results['ic'].mean():.4f}\n")
    report.append(f"**Median Sharpe:** {cross_pair_results['sharpe'].median():.2f}\n")
    report.append(f"**Mean Win Rate:** {cross_pair_results['win_rate'].mean():.1%}\n")
    
    report.append("\n### Pattern Detection Summary\n")
    
    report.append(f"**Average Exhaustion Detections:** {cross_pair_results['total_exhaustion'].mean():.0f} per pair\n")
    report.append(f"**Average Final Signals:** {cross_pair_results['n_signals'].mean():.0f} per pair\n")
    
    if 'total_signals' in cross_pair_results.columns and 'total_exhaustion' in cross_pair_results.columns:
        reduction = cross_pair_results['total_signals'].sum() / cross_pair_results['total_exhaustion'].sum() if cross_pair_results['total_exhaustion'].sum() > 0 else 0
        report.append(f"**Signal Reduction Ratio:** {reduction:.1%} (exhaustion → failure filter)\n")
    
    report.append("\n---\n")
    
    # Backtest Performance
    report.append("## 2. Backtest Performance\n")
    report.append("### Performance by Pair\n")
    
    report.append("\n" + backtest_summary.to_markdown(index=False) + "\n")
    
    # Load detailed trade statistics
    report.append("\n### Trade-Level Analysis\n")
    
    all_trades = []
    for csv_file in trades_dir.glob("trades_*.csv"):
        try:
            df = pd.read_csv(csv_file)
            df['pair'] = csv_file.stem.replace('trades_', '')
            all_trades.append(df)
        except:
            continue
    
    if all_trades:
        trades_df = pd.concat(all_trades, ignore_index=True)
        
        # Exit reason breakdown
        exit_counts = trades_df['exit_reason'].value_counts()
        report.append("\n**Exit Reason Distribution:**\n")
        for reason, count in exit_counts.items():
            pct = count / len(trades_df) * 100
            report.append(f"- {reason}: {count} ({pct:.1f}%)\n")
        
        # Holding period analysis
        avg_bars = trades_df['bars_held'].mean()
        report.append(f"\n**Average Holding Period:** {avg_bars:.1f} bars\n")
        
        # Direction balance
        long_trades = (trades_df['direction'] == 'LONG').sum()
        short_trades = (trades_df['direction'] == 'SHORT').sum()
        report.append(f"**Long/Short Balance:** {long_trades} long ({long_trades/len(trades_df):.0%}), {short_trades} short ({short_trades/len(trades_df):.0%})\n")
        
        # Cost analysis
        total_costs = trades_df['total_cost'].sum()
        avg_cost = trades_df['total_cost'].mean()
        report.append(f"\n**Transaction Costs:**\n")
        report.append(f"- Total costs: ${total_costs:.2f}\n")
        report.append(f"- Average cost per trade: ${avg_cost:.2f}\n")
        report.append(f"- Cost as % of total profit: {total_costs / trades_df['profit_dollars'].sum() * 100:.1f}%\n")
    
    report.append("\n---\n")
    
    # Risk Metrics
    report.append("## 3. Risk Management\n")
    report.append("### Position Sizing\n")
    report.append("- **Method:** Fixed fractional (1% risk per trade)\n")
    report.append("- **Initial Stop:** 10 pips\n")
    report.append("- **Trailing Stop:** 4-pip trigger, 3-pip trail\n")
    report.append("- **Max Holding Period:** 5 bars\n")
    report.append("- **Profit Target:** 15 pips (optional)\n")
    
    report.append("\n### Risk-Adjusted Returns\n")
    
    # Parse backtest summary for risk metrics
    for _, row in backtest_summary.iterrows():
        pair = row['Pair']
        report.append(f"\n**{pair}:**\n")
        report.append(f"- Sharpe Ratio: {row['Sharpe']}\n")
        report.append(f"- Max Drawdown: {row['Max DD']}\n")
        report.append(f"- Profit Factor: {row['Profit Factor']}\n")
    
    report.append("\n---\n")
    
    # Statistical Validation
    report.append("## 4. Statistical Validation\n")
    report.append("### Hypothesis Test Results\n")
    
    # IC significance
    significant = cross_pair_results[cross_pair_results['ic_pvalue'] < 0.05]
    report.append(f"\n**Information Coefficient (IC) Tests:**\n")
    report.append(f"- Pairs with significant IC: {len(significant)}/{len(cross_pair_results)}\n")
    report.append(f"- Mean IC (all pairs): {cross_pair_results['ic'].mean():.4f}\n")
    report.append(f"- Mean IC (significant pairs): {significant['ic'].mean():.4f}\n")
    
    # Stationarity
    stationary = cross_pair_results[cross_pair_results['is_stationary']]
    report.append(f"\n**Stationarity Tests (ADF + KPSS):**\n")
    report.append(f"- Stationary pairs: {len(stationary)}/{len(cross_pair_results)}\n")
    
    report.append("\n---\n")
    
    # Deployment Recommendations
    report.append("## 5. Deployment Recommendations\n")
    
    # Overall assessment
    if avg_win_rate >= 0.60 and significant_pairs >= len(cross_pair_results) * 0.5:
        report.append("### ✅ RECOMMENDED FOR DEPLOYMENT\n")
        report.append("\nThe exhaustion-failure-to-continue strategy demonstrates:\n")
        report.append(f"- Strong win rate ({avg_win_rate:.1%}) across multiple pairs\n")
        report.append(f"- Statistical significance in {significant_pairs/total_pairs:.0%} of pairs\n")
        report.append(f"- Consistent positive IC across instruments\n")
        
        report.append("\n**Suggested Implementation:**\n")
        
        # Recommend top pairs
        top_pairs = cross_pair_results.nlargest(5, 'ic')
        report.append("\n**Priority Pairs (by IC):**\n")
        for _, row in top_pairs.iterrows():
            report.append(f"1. {row['pair']} (IC: {row['ic']:.3f}, Win Rate: {row['win_rate']:.1%})\n")
        
        report.append("\n**Risk Parameters:**\n")
        report.append("- Start with 0.5% risk per trade (conservative)\n")
        report.append("- Scale to 1.0% after 20 successful trades\n")
        report.append("- Maximum 3 concurrent positions\n")
        report.append("- Daily loss limit: 3% of capital\n")
        
    elif avg_win_rate >= 0.55:
        report.append("### ⚠️ CONDITIONAL DEPLOYMENT\n")
        report.append("\nStrategy shows moderate performance. Recommend:\n")
        report.append("- Deploy only on pairs with significant IC (p < 0.05)\n")
        report.append("- Use conservative position sizing (0.5% risk)\n")
        report.append("- Monitor first 30 days closely\n")
        report.append("- Implement strict stop-loss discipline\n")
        
        # Best pairs only
        best_pairs = cross_pair_results[(cross_pair_results['ic_pvalue'] < 0.05) & (cross_pair_results['win_rate'] > 0.60)]
        if len(best_pairs) > 0:
            report.append(f"\n**Recommended Pairs ({len(best_pairs)} with p < 0.05 and win rate > 60%):**\n")
            for _, row in best_pairs.iterrows():
                report.append(f"- {row['pair']}\n")
    else:
        report.append("### ❌ NOT RECOMMENDED FOR DEPLOYMENT\n")
        report.append("\nStrategy performance is below acceptable thresholds:\n")
        report.append(f"- Average win rate ({avg_win_rate:.1%}) < 55%\n")
        report.append(f"- Limited statistical significance ({significant_pairs}/{total_pairs} pairs)\n")
        report.append("\n**Recommendations:**\n")
        report.append("- Re-optimize parameters (range expansion threshold, extreme zones)\n")
        report.append("- Test alternative failure definitions\n")
        report.append("- Consider adding regime filters\n")
        report.append("- Expand dataset for more robust testing\n")
    
    report.append("\n---\n")
    
    # Limitations and Future Work
    report.append("## 6. Limitations and Future Work\n")
    report.append("### Known Limitations\n")
    report.append("- **Sample Size:** Limited to ~2,000 bars per pair (hourly data)\n")
    report.append("- **Market Conditions:** Tested primarily on 2023-2025 data\n")
    report.append("- **Transaction Costs:** Simplified cost model (actual slippage may vary)\n")
    report.append("- **Correlation:** No explicit portfolio-level correlation management\n")
    
    report.append("\n### Future Enhancements\n")
    report.append("1. **Regime Detection:** Add HMM-based regime filters for range-bound periods\n")
    report.append("2. **Dynamic Sizing:** Adjust position sizes based on recent IC stability\n")
    report.append("3. **Cross-Pair Ensemble:** Combine signals across correlated pairs\n")
    report.append("4. **Intraday Optimization:** Test on 15-min or 5-min timeframes\n")
    report.append("5. **Machine Learning:** Use ML to optimize entry/exit timing\n")
    
    report.append("\n---\n")
    
    # Appendix
    report.append("## Appendix: Strategy Specification\n")
    report.append("### Pattern Definition\n")
    report.append("**EXHAUSTION (3 conditions):**\n")
    report.append("1. Range expansion > 0.8 × median(20)\n")
    report.append("2. Close in extreme zone (>0.65 or <0.35 of bar range)\n")
    report.append("3. ≥2 consecutive directional bars\n")
    
    report.append("\n**FAILURE TO CONTINUE:**\n")
    report.append("- Bullish exhaustion: Next bar closes below prior high\n")
    report.append("- Bearish exhaustion: Next bar closes above prior low\n")
    
    report.append("\n**SIGNAL:**\n")
    report.append("- Short (-1) on bullish failure\n")
    report.append("- Long (+1) on bearish failure\n")
    
    report.append("\n### Risk Management\n")
    report.append("- **Position Sizing:** size = (capital × 0.01) / (stop_pips × pip_size)\n")
    report.append("- **Stop Loss:** 10 pips (fixed initial)\n")
    report.append("- **Trailing Stop:** Activates at +4 pips profit, trails 3 pips behind\n")
    report.append("- **Time Exit:** Force close after 5 bars if neither stop nor target hit\n")
    report.append("- **Profit Target:** 15 pips (optional)\n")
    
    report.append("\n---\n")
    report.append(f"\n*Report generated by exhaustion-failure backtest system v1.0*")
    
    # Write report
    with open(output_path, 'w') as f:
        f.write('\n'.join(report))
    
    print(f"✓ Final report written to {output_path}")


def main():
    """Generate final report from existing results."""
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports"
    
    print("="*80)
    print("GENERATING FINAL REPORT")
    print("="*80)
    
    # Load cross-pair results
    cross_pair_file = reports_dir / "cross_pair_validation.csv"
    if not cross_pair_file.exists():
        print(f"✗ Cross-pair results not found: {cross_pair_file}")
        print("   Run scripts/validate_cross_pairs.py first")
        return
    
    cross_pair_results = pd.read_csv(cross_pair_file)
    print(f"✓ Loaded cross-pair validation results ({len(cross_pair_results)} pairs)")
    
    # Load backtest summary
    backtest_file = reports_dir / "backtest_summary.csv"
    if not backtest_file.exists():
        print(f"✗ Backtest results not found: {backtest_file}")
        print("   Run scripts/run_full_backtest.py first")
        return
    
    backtest_summary = pd.read_csv(backtest_file)
    print(f"✓ Loaded backtest summary ({len(backtest_summary)} pairs)")
    
    # Generate report
    output_path = reports_dir / "exhaustion_failure_final_results.md"
    generate_final_report(
        cross_pair_results=cross_pair_results,
        backtest_summary=backtest_summary,
        trades_dir=reports_dir,
        output_path=output_path
    )
    
    print(f"\n{'='*80}")
    print(f"Final report: {output_path}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
