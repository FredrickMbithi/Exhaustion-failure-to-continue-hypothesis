"""
Data forensics module for comprehensive data quality analysis.

Provides detailed analysis of FX data quality including spread distribution,
missing bars, timestamp continuity, price jumps, and overall quality scoring.
"""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats


class DataForensics:
    """
    Comprehensive data quality analysis and reporting.
    
    Generates detailed reports on:
    - Spread distribution and anomalies
    - Missing bar detection and analysis
    - Timestamp continuity and gaps
    - Price jump detection and classification
    - Overall quality score (0-100)
    
    Examples:
        >>> forensics = DataForensics()
        >>> report = forensics.generate_report(df, "EURUSD")
        >>> forensics.export_markdown(report, "reports/data_quality_report.md")
    """
    
    def __init__(self):
        """Initialize data forensics analyzer."""
        pass
    
    def generate_report(
        self,
        df: pd.DataFrame,
        pair_name: str = "UNKNOWN"
    ) -> Dict:
        """
        Generate comprehensive data quality report.
        
        Args:
            df: DataFrame with OHLC data and DatetimeIndex
            pair_name: Currency pair name for report
            
        Returns:
            Dictionary containing all quality metrics and analysis
            
        Examples:
            >>> report = forensics.generate_report(df, "EURUSD")
            >>> print(f"Quality Score: {report['quality_score']}/100")
        """
        report = {
            'pair_name': pair_name,
            'total_bars': len(df),
            'date_range': {
                'start': df.index[0].isoformat() if len(df) > 0 else None,
                'end': df.index[-1].isoformat() if len(df) > 0 else None,
                'days': (df.index[-1] - df.index[0]).days if len(df) > 0 else 0
            }
        }
        
        # Spread analysis
        if 'spread' in df.columns:
            report['spread_analysis'] = self._analyze_spread(df)
        else:
            report['spread_analysis'] = {'available': False}
        
        # Missing bars analysis
        report['missing_bars'] = self._analyze_missing_bars(df)
        
        # Timestamp continuity
        report['timestamp_gaps'] = self._analyze_timestamp_gaps(df)
        
        # Price jump detection
        report['price_jumps'] = self._analyze_price_jumps(df)
        
        # Return distribution
        report['return_distribution'] = self._analyze_return_distribution(df)
        
        # Calculate overall quality score
        report['quality_score'] = self._calculate_quality_score(report)
        
        return report
    
    def _analyze_spread(self, df: pd.DataFrame) -> Dict:
        """Analyze spread distribution and statistics."""
        spread = df['spread'].dropna()
        
        if len(spread) == 0:
            return {'available': False}
        
        # Calculate spread as percentage of mid price
        mid_price = (df['high'] + df['low']) / 2
        spread_pct = (spread / mid_price) * 100
        
        return {
            'available': True,
            'mean': float(spread.mean()),
            'median': float(spread.median()),
            'std': float(spread.std()),
            'min': float(spread.min()),
            'max': float(spread.max()),
            'p95': float(spread.quantile(0.95)),
            'mean_pct': float(spread_pct.mean()),
            'median_pct': float(spread_pct.median()),
            'negative_count': int((spread < 0).sum()),
            'zero_count': int((spread == 0).sum())
        }
    
    def _analyze_missing_bars(self, df: pd.DataFrame) -> Dict:
        """Analyze missing bars and gaps in data."""
        if len(df) == 0:
            return {'count': 0, 'percentage': 0.0}
        
        # Generate expected business days (FX trades Mon-Fri)
        expected_dates = pd.bdate_range(
            start=df.index[0],
            end=df.index[-1],
            freq='B'
        )
        
        missing = expected_dates.difference(df.index)
        missing_pct = (len(missing) / len(expected_dates)) * 100 if len(expected_dates) > 0 else 0
        
        return {
            'count': len(missing),
            'percentage': float(missing_pct),
            'expected_bars': len(expected_dates),
            'actual_bars': len(df),
            'sample_missing_dates': [ts.isoformat() for ts in missing[:10]]
        }
    
    def _analyze_timestamp_gaps(self, df: pd.DataFrame) -> Dict:
        """Analyze gaps between consecutive timestamps."""
        if len(df) < 2:
            return {}
        
        # Calculate time differences
        time_diffs = df.index.to_series().diff()
        
        # Convert to hours for analysis
        time_diffs_hours = time_diffs.dt.total_seconds() / 3600
        time_diffs_hours = time_diffs_hours.dropna()
        
        if len(time_diffs_hours) == 0:
            return {}
        
        return {
            'min_gap_hours': float(time_diffs_hours.min()),
            'max_gap_hours': float(time_diffs_hours.max()),
            'mean_gap_hours': float(time_diffs_hours.mean()),
            'median_gap_hours': float(time_diffs_hours.median()),
            'gaps_over_24h': int((time_diffs_hours > 24).sum()),
            'gaps_over_72h': int((time_diffs_hours > 72).sum())
        }
    
    def _analyze_price_jumps(self, df: pd.DataFrame) -> Dict:
        """Analyze price jumps and spikes."""
        if len(df) < 2:
            return {}
        
        # Calculate log returns
        returns = np.log(df['close'] / df['close'].shift(1))
        returns = returns.dropna()
        
        if len(returns) == 0:
            return {}
        
        # Calculate z-scores
        mean_return = returns.mean()
        std_return = returns.std()
        z_scores = (returns - mean_return) / std_return if std_return > 0 else pd.Series(0, index=returns.index)
        
        # Classify jumps
        spikes_5sigma = (np.abs(z_scores) > 5).sum()
        spikes_3sigma = (np.abs(z_scores) > 3).sum()
        
        return {
            'total_returns': len(returns),
            'spikes_5sigma': int(spikes_5sigma),
            'spikes_3sigma': int(spikes_3sigma),
            'spike_5sigma_pct': float((spikes_5sigma / len(returns)) * 100) if len(returns) > 0 else 0.0,
            'spike_3sigma_pct': float((spikes_3sigma / len(returns)) * 100) if len(returns) > 0 else 0.0,
            'max_positive_return': float(returns.max()),
            'max_negative_return': float(returns.min()),
            'max_abs_zscore': float(np.abs(z_scores).max()) if len(z_scores) > 0 else 0.0
        }
    
    def _analyze_return_distribution(self, df: pd.DataFrame) -> Dict:
        """Analyze return distribution statistics."""
        if len(df) < 2:
            return {}
        
        returns = np.log(df['close'] / df['close'].shift(1)).dropna()
        
        if len(returns) == 0:
            return {}
        
        # Calculate moments
        skewness = float(stats.skew(returns))
        kurtosis_val = float(stats.kurtosis(returns))
        
        # Jarque-Bera test for normality
        jb_stat, jb_pvalue = stats.jarque_bera(returns)
        
        return {
            'mean': float(returns.mean()),
            'std': float(returns.std()),
            'skewness': skewness,
            'kurtosis': kurtosis_val,
            'min': float(returns.min()),
            'max': float(returns.max()),
            'q25': float(returns.quantile(0.25)),
            'median': float(returns.median()),
            'q75': float(returns.quantile(0.75)),
            'jarque_bera_stat': float(jb_stat),
            'jarque_bera_pvalue': float(jb_pvalue),
            'is_normal': bool(jb_pvalue > 0.05)  # Accept normality if p > 0.05
        }
    
    def _calculate_quality_score(self, report: Dict) -> float:
        """
        Calculate overall data quality score (0-100).
        
        Deductions:
        - Missing data: -10 per 1% missing
        - Spikes (>5σ): -20 if >0.1% of data
        - Spread anomalies: -10 if negative spreads found
        - Large gaps: -5 per gap >72 hours
        
        Args:
            report: Complete forensics report
            
        Returns:
            Quality score from 0 to 100
        """
        score = 100.0
        
        # Deduct for missing data
        missing_pct = report['missing_bars'].get('percentage', 0)
        score -= missing_pct * 10  # -10 per 1% missing
        
        # Deduct for spikes
        spike_pct = report['price_jumps'].get('spike_5sigma_pct', 0)
        if spike_pct > 0.1:  # More than 0.1% are extreme spikes
            score -= 20
        
        # Deduct for spread anomalies
        spread_analysis = report.get('spread_analysis', {})
        if spread_analysis.get('available', False):
            if spread_analysis.get('negative_count', 0) > 0:
                score -= 10
        
        # Deduct for large timestamp gaps
        gaps_72h = report['timestamp_gaps'].get('gaps_over_72h', 0)
        score -= gaps_72h * 5
        
        # Ensure score is within bounds
        score = max(0.0, min(100.0, score))
        
        return float(score)
    
    def export_markdown(
        self,
        report: Dict,
        output_path: str = "reports/data_quality_report.md"
    ) -> None:
        """
        Export forensics report as formatted Markdown.
        
        Args:
            report: Report dictionary from generate_report()
            output_path: Path to save Markdown file
            
        Examples:
            >>> forensics.export_markdown(report, "reports/eurusd_quality.md")
        """
        md_lines = []
        
        # Header
        md_lines.append(f"# Data Quality Report: {report['pair_name']}")
        md_lines.append("")
        md_lines.append(f"**Generated:** {pd.Timestamp.now(tz='UTC').isoformat()}")
        md_lines.append("")
        
        # Overall quality score
        score = report['quality_score']
        score_emoji = "🟢" if score >= 90 else "🟡" if score >= 70 else "🔴"
        md_lines.append(f"## Overall Quality Score: {score:.1f}/100 {score_emoji}")
        md_lines.append("")
        
        # Date range
        md_lines.append("## Dataset Information")
        md_lines.append("")
        md_lines.append(f"- **Total Bars:** {report['total_bars']:,}")
        md_lines.append(f"- **Date Range:** {report['date_range']['start']} to {report['date_range']['end']}")
        md_lines.append(f"- **Duration:** {report['date_range']['days']} days")
        md_lines.append("")
        
        # Missing bars
        md_lines.append("## Missing Bars Analysis")
        md_lines.append("")
        missing = report['missing_bars']
        md_lines.append(f"- **Missing Bars:** {missing['count']} ({missing['percentage']:.2f}%)")
        md_lines.append(f"- **Expected Bars:** {missing['expected_bars']}")
        md_lines.append(f"- **Actual Bars:** {missing['actual_bars']}")
        if missing['count'] > 0:
            md_lines.append(f"- **Sample Missing Dates:** {', '.join(missing['sample_missing_dates'][:5])}")
        md_lines.append("")
        
        # Timestamp gaps
        md_lines.append("## Timestamp Continuity")
        md_lines.append("")
        gaps = report['timestamp_gaps']
        if gaps:
            md_lines.append(f"- **Min Gap:** {gaps.get('min_gap_hours', 0):.1f} hours")
            md_lines.append(f"- **Max Gap:** {gaps.get('max_gap_hours', 0):.1f} hours")
            md_lines.append(f"- **Mean Gap:** {gaps.get('mean_gap_hours', 0):.1f} hours")
            md_lines.append(f"- **Gaps >24h:** {gaps.get('gaps_over_24h', 0)}")
            md_lines.append(f"- **Gaps >72h:** {gaps.get('gaps_over_72h', 0)}")
        md_lines.append("")
        
        # Price jumps
        md_lines.append("## Price Jump Detection")
        md_lines.append("")
        jumps = report['price_jumps']
        if jumps:
            md_lines.append(f"- **Total Returns Analyzed:** {jumps.get('total_returns', 0):,}")
            md_lines.append(f"- **Spikes >5σ:** {jumps.get('spikes_5sigma', 0)} ({jumps.get('spike_5sigma_pct', 0):.3f}%)")
            md_lines.append(f"- **Spikes >3σ:** {jumps.get('spikes_3sigma', 0)} ({jumps.get('spike_3sigma_pct', 0):.3f}%)")
            md_lines.append(f"- **Max Positive Return:** {jumps.get('max_positive_return', 0):.4f}")
            md_lines.append(f"- **Max Negative Return:** {jumps.get('max_negative_return', 0):.4f}")
            md_lines.append(f"- **Max |Z-Score|:** {jumps.get('max_abs_zscore', 0):.2f}")
        md_lines.append("")
        
        # Return distribution
        md_lines.append("## Return Distribution")
        md_lines.append("")
        ret_dist = report['return_distribution']
        if ret_dist:
            md_lines.append(f"- **Mean:** {ret_dist.get('mean', 0):.6f}")
            md_lines.append(f"- **Std Dev:** {ret_dist.get('std', 0):.6f}")
            md_lines.append(f"- **Skewness:** {ret_dist.get('skewness', 0):.3f}")
            md_lines.append(f"- **Kurtosis:** {ret_dist.get('kurtosis', 0):.3f}")
            md_lines.append(f"- **Jarque-Bera p-value:** {ret_dist.get('jarque_bera_pvalue', 0):.4f}")
            md_lines.append(f"- **Normal Distribution:** {'Yes' if ret_dist.get('is_normal', False) else 'No'}")
        md_lines.append("")
        
        # Spread analysis
        spread = report['spread_analysis']
        if spread.get('available', False):
            md_lines.append("## Spread Analysis")
            md_lines.append("")
            md_lines.append(f"- **Mean Spread:** {spread.get('mean', 0):.4f}")
            md_lines.append(f"- **Median Spread:** {spread.get('median', 0):.4f}")
            md_lines.append(f"- **Std Dev:** {spread.get('std', 0):.4f}")
            md_lines.append(f"- **95th Percentile:** {spread.get('p95', 0):.4f}")
            md_lines.append(f"- **Mean % of Price:** {spread.get('mean_pct', 0):.4f}%")
            md_lines.append(f"- **Negative Spreads:** {spread.get('negative_count', 0)}")
            md_lines.append(f"- **Zero Spreads:** {spread.get('zero_count', 0)}")
            md_lines.append("")
        
        # Quality assessment
        md_lines.append("## Quality Assessment")
        md_lines.append("")
        if score >= 90:
            md_lines.append("✅ **Excellent** - Data quality is very high, suitable for production use.")
        elif score >= 70:
            md_lines.append("⚠️ **Good** - Data quality is acceptable with minor issues to note.")
        elif score >= 50:
            md_lines.append("⚠️ **Fair** - Data has some quality issues that should be addressed.")
        else:
            md_lines.append("❌ **Poor** - Significant data quality issues detected. Review carefully.")
        md_lines.append("")
        
        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write('\n'.join(md_lines))
        
        print(f"Data quality report exported to: {output_path}")
