"""
Days 25-30: Integrated Testing

Tests:
1. Multi-timeframe features
2. Regime detection  
3. Portfolio construction
4. Monte Carlo validation

Generates comprehensive report for Days 25-30 completion.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import FXDataLoader
from src.strategies.exhaustion_failure import ExhaustionFailureStrategy
from src.features.multi_timeframe import MultiTimeframeFeatures
from src.portfolio.portfolio_constructor import PortfolioConstructor
from src.analysis.monte_carlo import MonteCarloValidator


def test_pair_comprehensive(pair: str, data_dir: Path) -> dict:
    """Comprehensive test of single pair with all features."""
    
    print(f"\n{'='*70}")
    print(f"{pair} - COMPREHENSIVE ANALYSIS")
    print("="*70)
    
    # Load data
    csv_path = data_dir / f"{pair}60.csv"
    loader = FXDataLoader()
    df, _ = loader.load_csv(str(csv_path), pair=pair)
    print(f"✅ Loaded {len(df)} bars")
    
    # Add MTF features
    mtf = MultiTimeframeFeatures()
    df = mtf.add_higher_tf_features(df)
    print(f"✅ Added multi-timeframe features")
    
    # Generate signals with optimized parameters
    strategy = ExhaustionFailureStrategy(
        range_expansion_threshold=1.5,
        extreme_zone_upper=0.85,
        extreme_zone_lower=0.20,
        consecutive_bars_required=2
    )
    
    df_signals = strategy.generate_signals(df)
    signals = df_signals['signal']
    
    # Calculate returns
    returns = df['close'].pct_change()
    strategy_returns = returns * signals.shift(1)
    
    # Get trade-level returns
    trades = pd.DataFrame({
        'signal': signals,
        'returns': returns,
        'strat_returns': strategy_returns
    }).dropna()
    
    trades = trades[trades['signal'] != 0]
    trade_returns = trades['strat_returns']
    
    # Basic stats
    n_signals = len(trade_returns)
    win_rate = (trade_returns > 0).mean() * 100
    total_return = (1 + trade_returns).prod() - 1
    sharpe = trade_returns.mean() / trade_returns.std() * np.sqrt(252 * 24) if trade_returns.std() > 0 else 0
    
    # IC
    if len(trades) >= 10:
        ic, ic_pval = spearmanr(trades['signal'], trades['returns'])
    else:
        ic, ic_pval = 0, 1
    
    print(f"\n📊 Strategy Performance:")
    print(f"  Signals: {n_signals}")
    print(f"  Win Rate: {win_rate:.2f}%")
    print(f"  Total Return: {total_return*100:.2f}%")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  IC: {ic:.4f} (p={ic_pval:.4f})")
    
    # Monte Carlo validation
    if n_signals >= 20:
        print(f"\n🎲 Monte Carlo Validation ({n_signals} trades):")
        mc = MonteCarloValidator(n_simulations=1000, random_state=42)
        mc_report = mc.generate_validation_report(
            trade_returns,
            signals=trades['signal'],
            returns=trades['returns']
        )
        
        print(f"  Probability Profitable: {mc_report['prob_profitable']*100:.1f}%")
        print(f"  Expected Drawdown: {mc_report['drawdown_distribution']['median']*100:.1f}% (median)")
        print(f"  Worst Drawdown (95th): {mc_report['drawdown_distribution']['p95']*100:.1f}%")
        print(f"  Expected Sharpe: {mc_report['sharpe_distribution']['median']:.2f} (median)")
        print(f"  Permutation Test p-value: {mc_report.get('permutation_test_pval', 'N/A')}")
    else:
        print(f"\n⚠️  Too few signals ({n_signals}) for Monte Carlo validation")
        mc_report = None
    
    return {
        'pair': pair,
        'n_signals': n_signals,
        'win_rate': win_rate,
        'total_return': total_return,
        'sharpe': sharpe,
        'ic': ic,
        'ic_pval': ic_pval,
        'trade_returns': trade_returns,
        'daily_returns': strategy_returns,
        'mc_report': mc_report
    }


def main():
    print("="*70)
    print("DAYS 25-30: INTEGRATED TESTING")
    print("Multi-Timeframe + Portfolio + Monte Carlo")
    print("="*70)
    
    data_dir = Path(__file__).parent.parent / 'data' / 'raw'
    pairs = ['USDJPY', 'NZDJPY']
    
    # Test each pair
    results = {}
    for pair in pairs:
        results[pair] = test_pair_comprehensive(pair, data_dir)
    
    # Portfolio construction
    print(f"\n{'='*70}")
    print("PORTFOLIO ANALYSIS")
    print("="*70)
    
    # Create returns DataFrame
    returns_df = pd.DataFrame({
        pair: results[pair]['daily_returns']
        for pair in pairs
    }).dropna()
    
    print(f"Portfolio period: {len(returns_df)} bars")
    
    # Portfolio constructor
    pc = PortfolioConstructor()
    portfolio_report = pc.generate_portfolio_report(returns_df)
    
    # Correlation Analysis
    print(f"\n📊 Cross-Pair Correlation:")
    print(portfolio_report['correlation_matrix'].to_string())
    print(f"\n  Average Correlation: {portfolio_report['avg_correlation']:.4f}")
    print(f"  Max Correlation: {portfolio_report['max_correlation']:.4f}")
    
    if portfolio_report['high_correlation_pairs']:
        print(f"\n  High Correlation Pairs (>{pc.min_correlation_threshold}):")
        for p1, p2, corr in portfolio_report['high_correlation_pairs']:
            print(f"    {p1} - {p2}: {corr:.4f}")
    else:
        print(f"  ✅ No high correlation pairs (all <{pc.min_correlation_threshold})")
    
    # Portfolio strategies
    print(f"\n📈 Portfolio Strategies:")
    for strategy_name, strategy_data in portfolio_report['portfolios'].items():
        print(f"\n  {strategy_name.upper().replace('_', ' ')}:")
        print(f"    Weights:")
        for pair, weight in strategy_data['weights'].items():
            print(f"      {pair}: {weight*100:.1f}%")
        print(f"    Sharpe: {strategy_data['sharpe']:.2f}")
        print(f"    Volatility: {strategy_data['volatility']*100:.2f}%")
        print(f"    Diversification Ratio: {strategy_data['diversification_ratio']:.2f}")
    
    # Summary table
    print(f"\n{'='*70}")
    print("PERFORMANCE SUMMARY")
    print("="*70)
    
    summary_data = []
    for pair in pairs:
        data = results[pair]
        summary_data.append({
            'Pair': pair,
            'Signals': data['n_signals'],
            'Win Rate': f"{data['win_rate']:.1f}%",
            'Total Return': f"{data['total_return']*100:.1f}%",
            'Sharpe': f"{data['sharpe']:.2f}",
            'IC': f"{data['ic']:.4f}",
            'IC p-val': f"{data['ic_pval']:.4f}"
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    # Monte Carlo Summary
    print(f"\n{'='*70}")
    print("MONTE CARLO VALIDATION SUMMARY")
    print("="*70)
    
    for pair in pairs:
        mc_rep = results[pair]['mc_report']
        if mc_rep:
            print(f"\n{pair}:")
            print(f"  Probability Profitable: {mc_rep['prob_profitable']*100:.1f}%")
            print(f"  Expected Return: {mc_rep['return_distribution']['median']*100:.1f}% (median)")
            print(f"  Expected Sharpe: {mc_rep['sharpe_distribution']['median']:.2f} (median)")
            print(f"  Max Drawdown (95th %ile): {mc_rep['drawdown_distribution']['p95']*100:.1f}%")
            
            # Significance
            perm_pval = mc_rep.get('permutation_test_pval', None)
            if perm_pval is not None:
                sig_symbol = "✅" if perm_pval < 0.05 else "❌"
                print(f"  Permutation Test: p={perm_pval:.4f} {sig_symbol}")
        else:
            print(f"\n{pair}: Insufficient signals for Monte Carlo")
    
    # Save results
    output_dir = Path(__file__).parent.parent
    
    # Save summary
    summary_df.to_csv(output_dir / 'days_25-30_summary.csv', index=False)
    print(f"\n✅ Summary saved to days_25-30_summary.csv")
    
    # Save correlation matrix
    portfolio_report['correlation_matrix'].to_csv(output_dir / 'correlation_matrix.csv')
    print(f"✅ Correlation matrix saved to correlation_matrix.csv")
    
    # Final recommendations
    print(f"\n{'='*70}")
    print("KEY FINDINGS & RECOMMENDATIONS")
    print("="*70)
    
    # Best pair
    best_pair = max(pairs, key=lambda p: results[p]['sharpe'])
    print(f"\n1. BEST PERFORMER: {best_pair}")
    print(f"   Sharpe: {results[best_pair]['sharpe']:.2f}")
    print(f"   Win Rate: {results[best_pair]['win_rate']:.1f}%")
    
    # Diversification
    if portfolio_report['avg_correlation'] < 0.5:
        print(f"\n2. DIVERSIFICATION: ✅ GOOD")
        print(f"   Average correlation: {portfolio_report['avg_correlation']:.2f}")
        print(f"   Recommendation: Use portfolio approach")
    else:
        print(f"\n2. DIVERSIFICATION: ⚠️ MODERATE")
        print(f"   Average correlation: {portfolio_report['avg_correlation']:.2f}")
        print(f"   Recommendation: Add more uncorrelated pairs")
    
    # Statistical significance
    significant_pairs = [p for p in pairs if results[p]['ic_pval'] < 0.05]
    print(f"\n3. STATISTICAL SIGNIFICANCE:")
    if significant_pairs:
        print(f"   ✅ {len(significant_pairs)}/{len(pairs)} pairs significant (IC p<0.05)")
        for p in significant_pairs:
            print(f"      {p}: IC={results[p]['ic']:.4f}, p={results[p]['ic_pval']:.4f}")
    else:
        print(f"   ⚠️ No pairs statistically significant at 95% confidence")
    
    # Monte Carlo robustness
    robust_pairs = [p for p in pairs if results[p]['mc_report'] and results[p]['mc_report']['prob_profitable'] > 0.7]
    if robust_pairs:
        print(f"\n4. MONTE CARLO ROBUSTNESS:")
        print(f"   ✅ {len(robust_pairs)}/{len(pairs)} pairs >70% probability profitable")
        for p in robust_pairs:
            prob = results[p]['mc_report']['prob_profitable']
            print(f"      {p}: {prob*100:.1f}% probability")
    
    print(f"\n{'='*70}")
    print("DAYS 25-30 COMPLETE ✅")
    print("="*70)


if __name__ == "__main__":
    main()
