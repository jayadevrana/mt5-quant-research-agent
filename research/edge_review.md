# Evidence-Backed FX Edge Review

This project does not assume a profitable edge exists. It converts plausible edge categories into testable rules, then rejects them unless the data survives transaction costs, out-of-sample validation, stress tests, and Monte Carlo drawdown analysis.

Evidence anchors:

- BIS 2025 Triennial Survey reports OTC FX turnover of about USD 9.6 trillion per day, with the US dollar on one side of 89.2% of trades. This supports choosing liquid USD majors first, not exotic or marketing-driven symbols. Source: https://www.bis.org/statistics/rpfx25_fx.htm
- CFTC warns that roughly two out of three retail FX traders lose money each quarter and that signal/software claims are common fraud patterns. Source: https://www.cftc.gov/LearnAndProtect/forexfrauds
- Time-series momentum and trend-following evidence is strongest across diversified futures portfolios and long samples, not necessarily one retail spot-FX pair on M15. Sources: https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf and https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing/
- FX market-making and HFT price-discovery edges are real but infrastructure-heavy and generally inaccessible to a retail MT5 account. Sources: https://www.bis.org/publ/qtrpdf/r_qt2512v.htm and https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4349184
- Currency carry has historical profitability evidence, but crash/peso-event risk and swap dependence make it unsuitable as the first intraday MT5 agent. Source: https://www.nber.org/papers/w17278

| Edge Type | Who Uses It | Why It Works | Retail Feasibility | MT5 Feasibility | Main Risk | Testable? | Verdict |
|---|---|---|---|---|---|---|---|
| Time-series trend | CTAs, systematic macro | Behavioral/risk premia, slow information diffusion | Medium | Medium | Whipsaw, crowding | Yes | Primary research candidate |
| Intraday breakout | FX desks, prop traders | Session liquidity and volatility expansion | Medium | High | False breakouts, spread | Yes | Test, not assume |
| Carry | Macro/carry funds | Rate differential and risk premium | Low/Medium | Medium | Crash risk, swap changes | Yes | Research only, not v1 |
| Market making | Banks, PTFs | Spread capture, inventory control | Very low | Low | Adverse selection | Yes | Reject for retail MT5 |
| Statistical arbitrage | Quant firms | Cross-market relative value | Low | Low/Medium | Data/execution dependency | Yes | Reject for v1 |
| Volatility trading | Options desks/funds | Vol risk premium/skew | Low | Low | Options access/model risk | Partly | Reject for MT5 spot v1 |
| Verified discretionary retail | Rare audited traders | Execution discipline/specialization | Low | Medium | Survivorship bias | Hard | Do not copy claims |

## Practical Conclusion

The first production candidate should be simple, cost-aware, and falsifiable: a higher-timeframe trend pullback with volatility filtering on EURUSD M15. It should be rejected unless it survives robust local MT5 data testing. Intraday breakout variants remain research candidates, not assumptions.
