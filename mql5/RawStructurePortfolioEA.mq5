//+------------------------------------------------------------------+
//| RawStructurePortfolioEA.mq5                                      |
//| Two-module non-indicator MT5 EA suite: trend expansion + range.  |
//| Signals use raw OHLC structure, spread, session and risk gates.  |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "Raw OHLC trend/range EA suite with hard SL/TP, 5R target and master risk controls."

#include <Trade/Trade.mqh>

enum RegimeState
{
   REGIME_UNSAFE = 0,
   REGIME_TREND  = 1,
   REGIME_RANGE  = 2
};

enum StrategyFamily
{
   FAMILY_NONE  = 0,
   FAMILY_TREND = 1,
   FAMILY_RANGE = 2
};

enum TradeDirection
{
   DIR_NONE  = 0,
   DIR_LONG  = 1,
   DIR_SHORT = -1
};

input group "Core"
input bool EnableTrading = false;
input long MagicNumber = 26052501;
input string SymbolsWhitelist = "EURUSD,GBPUSD,USDJPY,USDCHF,USDCAD,AUDUSD,NZDUSD,EURJPY,GBPJPY,EURGBP,AUDJPY,AUDNZD";
input ENUM_TIMEFRAMES StructureTimeframe = PERIOD_H4;
input ENUM_TIMEFRAMES ExecutionTimeframe = PERIOD_H1;
input double InitialCapital = 10000.0;
input double RR = 5.0;

input group "Risk"
input double BaseRiskPct = 0.25;
input double MaxRiskPerTradePct = 0.50;
input double MaxRiskPerSymbolPct = 0.50;
input double MaxRiskPerCurrencyPct = 1.00;
input double MaxRiskPerStrategyPct = 1.25;
input double MaxPortfolioOpenRiskPct = 2.00;
input double DailyProfitTargetPct = 1.00;
input double DailyLossLimitPct = 1.50;
input double WeeklyLossLimitPct = 3.00;
input double MonthlyLossLimitPct = 6.00;
input double DeRiskDrawdownPct = 5.00;
input double RecoveryDisableDrawdownPct = 7.50;
input double MaxDrawdownPct = 10.00;
input int MaxConsecutiveLosses = 8;

input group "Recovery"
input bool UseRecoveryMode = true;
input double RecoveryL1RiskPct = 0.30;
input double RecoveryL2RiskPct = 0.35;
input double RecoveryL3RiskPct = 0.40;

input group "Structure"
input int SwingConfirmBars = 3;
input int MedianLookbackBars = 50;
input int AnalysisLookbackBars = 220;
input double BosBufferMedianRangePct = 0.20;
input double SlBufferMedianRangePct = 0.15;
input double DisplacementBodyMultiplier = 1.20;
input double DisplacementCloseMoveMultiplier = 0.70;
input double RejectionWickMinPct = 0.40;
input double AbnormalCandleMultiplier = 3.50;
input int MaxRetestBars = 8;
input int LossCooldownBars = 5;

input group "Range"
input int RangeMinBars = 40;
input int RangeMaxBars = 150;
input double RangeContainmentMinPct = 70.0;
input int RangeTouchesPerSideMin = 2;
input double RangeBoundaryToleranceMedianPct = 0.60;
input double RangeDangerZonePct = 0.10;
input double RangeMinWidthMedianMultiple = 6.0;

input group "Execution Filters"
input int MaxDeviationPoints = 20;
input double MaxSpreadToRiskPct = 8.0;
input double MaxSlippageToRiskPct = 5.0;
input double EstimatedCommissionRoundTurnPerLot = 0.0;
input double EstimatedSlippagePoints = 2.0;
input double MinFreeMarginMultiple = 5.0;
input double MaxUsedMarginPct = 30.0;
input bool UseNewsFilter = false;
input int NoTradeBeforeNewsMinutes = 30;
input int NoTradeAfterNewsMinutes = 30;
input int AvoidRolloverMinutes = 20;
input int NoTradeFridayAfterUTC = 20;

input group "Management"
input bool UseBreakEven = true;
input bool UseStructureTrailing = true;
input double BreakEvenAfterR = 1.20;
input double TrailAfterTrendR = 2.00;
input double TrailAfterRangeR = 3.00;
input double LockOneRAfterR = 3.00;
input int MinorSwingBars = 2;

input group "Logging"
input bool WriteCsvLog = true;
input string CsvLogFileName = "RawStructurePortfolioEA_log.csv";

struct SymbolState
{
   string symbol;
   datetime last_bar_time;
   int trend_setup_dir;
   int trend_setup_bars_left;
   int trend_setup_stage;
   double trend_level;
   double trend_rejection_high;
   double trend_rejection_low;
   double trend_origin_extreme;
   int range_setup_dir;
   int range_setup_bars_left;
   int range_setup_stage;
   double range_upper_mid;
   double range_lower_mid;
   double range_rejection_high;
   double range_rejection_low;
   double range_sweep_extreme;
   datetime cooldown_until_bar;
};

struct MarketStats
{
   double median_range;
   double median_body;
   double spread_price;
   double spread_points;
   double point;
   double tick_size;
   double tick_value;
   double volume_min;
   double volume_max;
   double volume_step;
   int digits;
};

struct SwingInfo
{
   double last_high;
   double prev_high;
   double last_low;
   double prev_low;
   int last_high_index;
   int prev_high_index;
   int last_low_index;
   int prev_low_index;
   bool has_highs;
   bool has_lows;
};

struct RangeInfo
{
   bool valid;
   double upper_mid;
   double lower_mid;
   double width;
   double containment_pct;
   int upper_touches;
   int lower_touches;
   string reason;
};

struct Candidate
{
   bool valid;
   string symbol;
   int direction;
   int family;
   double entry;
   double sl;
   double tp;
   double risk_price;
   double lots;
   double risk_money;
   bool recovery;
   string reason;
};

CTrade g_trade;
SymbolState g_states[];
string g_symbols[];
int g_log_handle = INVALID_HANDLE;
bool g_slippage_degraded = false;

string TrimString(string value)
{
   string out = value;
   StringTrimLeft(out);
   StringTrimRight(out);
   return out;
}

string FamilyName(const int family)
{
   if(family == FAMILY_TREND) return "TREND";
   if(family == FAMILY_RANGE) return "RANGE";
   return "NONE";
}

string DirectionName(const int direction)
{
   if(direction == DIR_LONG) return "LONG";
   if(direction == DIR_SHORT) return "SHORT";
   return "NONE";
}

string RegimeName(const int regime)
{
   if(regime == REGIME_TREND) return "TREND";
   if(regime == REGIME_RANGE) return "RANGE";
   return "UNSAFE";
}

double PercentToFraction(const double pct)
{
   return pct / 100.0;
}

double EffectiveCapital()
{
   return MathMin(AccountInfoDouble(ACCOUNT_EQUITY), AccountInfoDouble(ACCOUNT_BALANCE));
}

datetime TradeServerFromUtc(datetime utc_time)
{
   datetime server_now = TimeTradeServer();
   if(server_now <= 0) server_now = TimeCurrent();
   return utc_time + (server_now - TimeGMT());
}

datetime UtcFromTradeServer(datetime server_time)
{
   datetime server_now = TimeTradeServer();
   if(server_now <= 0) server_now = TimeCurrent();
   return server_time - (server_now - TimeGMT());
}

datetime UtcDayStart()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   return StructToTime(dt);
}

datetime UtcWeekStart()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   datetime today = StructToTime(dt);
   int dow = dt.day_of_week;
   int days_back = (dow == 0 ? 6 : dow - 1);
   return today - days_back * 86400;
}

datetime UtcMonthStart()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   dt.day = 1;
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   return StructToTime(dt);
}

double NormalizePrice(const string symbol, const double price)
{
   double tick = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(tick <= 0.0) tick = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(tick <= 0.0) return NormalizeDouble(price, digits);
   return NormalizeDouble(MathRound(price / tick) * tick, digits);
}

double NormalizeLots(const string symbol, const double lots)
{
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0) step = 0.01;
   double normalized = MathFloor(lots / step) * step;
   normalized = MathMax(min_lot, MathMin(max_lot, normalized));
   int digits = 0;
   double probe = step;
   while(digits < 8 && MathAbs(probe - MathRound(probe)) > 0.00000001)
   {
      probe *= 10.0;
      digits++;
   }
   return NormalizeDouble(normalized, digits);
}

void LogEvent(const string event_type, const string symbol, const string family, const string direction, const string reason,
              const double entry = 0.0, const double sl = 0.0, const double tp = 0.0, const double lots = 0.0,
              const double risk_money = 0.0, const double spread_points = 0.0)
{
   string line = StringFormat("%s %s %s %s %s %s entry=%.8f sl=%.8f tp=%.8f lots=%.2f risk=%.2f spread=%.1f",
                              TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS), event_type, symbol, family, direction,
                              reason, entry, sl, tp, lots, risk_money, spread_points);
   Print(line);

   if(WriteCsvLog && g_log_handle != INVALID_HANDLE)
   {
      FileWrite(g_log_handle,
                TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS),
                event_type, symbol, family, direction, reason,
                DoubleToString(entry, 8), DoubleToString(sl, 8), DoubleToString(tp, 8),
                DoubleToString(lots, 2), DoubleToString(risk_money, 2), DoubleToString(spread_points, 1));
      FileFlush(g_log_handle);
   }
}

bool LoadRates(const string symbol, const ENUM_TIMEFRAMES timeframe, const int count, MqlRates &rates[])
{
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(symbol, timeframe, 0, count, rates);
   return copied >= MathMin(count, 100);
}

void SortDoubles(double &values[], const int count)
{
   for(int i = 1; i < count; i++)
   {
      double key = values[i];
      int j = i - 1;
      while(j >= 0 && values[j] > key)
      {
         values[j + 1] = values[j];
         j--;
      }
      values[j + 1] = key;
   }
}

double MedianOf(double &values[], const int count)
{
   if(count <= 0) return 0.0;
   SortDoubles(values, count);
   if((count % 2) == 1) return values[count / 2];
   return (values[count / 2 - 1] + values[count / 2]) / 2.0;
}

bool LoadMarketStats(const string symbol, const MqlRates &rates[], const int lookback, MarketStats &stats)
{
   int bars = ArraySize(rates);
   int n = MathMin(lookback, bars - 2);
   if(n < 10) return false;

   double ranges[];
   double bodies[];
   ArrayResize(ranges, n);
   ArrayResize(bodies, n);
   for(int i = 1; i <= n; i++)
   {
      ranges[i - 1] = MathMax(0.0, rates[i].high - rates[i].low);
      bodies[i - 1] = MathAbs(rates[i].close - rates[i].open);
   }

   stats.median_range = MedianOf(ranges, n);
   stats.median_body = MedianOf(bodies, n);
   stats.point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   stats.tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   stats.tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(stats.tick_value <= 0.0) stats.tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   stats.volume_min = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   stats.volume_max = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   stats.volume_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   stats.digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick)) return false;
   stats.spread_price = MathMax(0.0, tick.ask - tick.bid);
   stats.spread_points = (stats.point > 0.0 ? stats.spread_price / stats.point : 0.0);
   return stats.median_range > 0.0 && stats.point > 0.0 && stats.tick_size > 0.0 && stats.tick_value > 0.0;
}

bool IsSwingHigh(const MqlRates &rates[], const int index, const int wing)
{
   for(int i = 1; i <= wing; i++)
   {
      if(rates[index].high <= rates[index - i].high) return false;
      if(rates[index].high <= rates[index + i].high) return false;
   }
   return true;
}

bool IsSwingLow(const MqlRates &rates[], const int index, const int wing)
{
   for(int i = 1; i <= wing; i++)
   {
      if(rates[index].low >= rates[index - i].low) return false;
      if(rates[index].low >= rates[index + i].low) return false;
   }
   return true;
}

SwingInfo DetectSwings(const MqlRates &rates[], const int wing, const int lookback)
{
   SwingInfo s;
   s.last_high = s.prev_high = s.last_low = s.prev_low = 0.0;
   s.last_high_index = s.prev_high_index = s.last_low_index = s.prev_low_index = -1;
   s.has_highs = false;
   s.has_lows = false;

   int bars = ArraySize(rates);
   int max_i = MathMin(lookback, bars - wing - 1);
   for(int i = wing + 1; i <= max_i; i++)
   {
      if(IsSwingHigh(rates, i, wing))
      {
         if(s.last_high_index < 0)
         {
            s.last_high = rates[i].high;
            s.last_high_index = i;
         }
         else if(s.prev_high_index < 0)
         {
            s.prev_high = rates[i].high;
            s.prev_high_index = i;
            s.has_highs = true;
         }
      }
      if(IsSwingLow(rates, i, wing))
      {
         if(s.last_low_index < 0)
         {
            s.last_low = rates[i].low;
            s.last_low_index = i;
         }
         else if(s.prev_low_index < 0)
         {
            s.prev_low = rates[i].low;
            s.prev_low_index = i;
            s.has_lows = true;
         }
      }
      if(s.has_highs && s.has_lows) break;
   }
   return s;
}

double BosBuffer(const MarketStats &stats)
{
   double median_part = BosBufferMedianRangePct * stats.median_range;
   double spread_part = 2.0 * stats.spread_price;
   double min_part = 3.0 * stats.point;
   return MathMax(spread_part, MathMax(median_part, min_part));
}

double SlBuffer(const MarketStats &stats)
{
   double median_part = SlBufferMedianRangePct * stats.median_range;
   double spread_part = 2.0 * stats.spread_price;
   double slippage_part = EstimatedSlippagePoints * stats.point;
   return MathMax(spread_part, MathMax(median_part, slippage_part));
}

double CloseLocation(const MqlRates &bar)
{
   double range = bar.high - bar.low;
   if(range <= 0.0) return 0.5;
   return (bar.close - bar.low) / range;
}

bool IsAbnormalCandle(const MqlRates &bar, const MarketStats &stats)
{
   return (bar.high - bar.low) > AbnormalCandleMultiplier * stats.median_range;
}

bool HasBullishDisplacement(const MqlRates &rates[], const MarketStats &stats)
{
   double body = MathAbs(rates[1].close - rates[1].open);
   double close_move = MathAbs(rates[1].close - rates[2].close);
   if(body < DisplacementBodyMultiplier * stats.median_body) return false;
   if(close_move < DisplacementCloseMoveMultiplier * stats.median_range) return false;
   if(CloseLocation(rates[1]) < 0.65) return false;
   double upper_wick = rates[1].high - MathMax(rates[1].open, rates[1].close);
   if(upper_wick > 0.50 * (rates[1].high - rates[1].low)) return false;
   return true;
}

bool HasBearishDisplacement(const MqlRates &rates[], const MarketStats &stats)
{
   double body = MathAbs(rates[1].close - rates[1].open);
   double close_move = MathAbs(rates[1].close - rates[2].close);
   if(body < DisplacementBodyMultiplier * stats.median_body) return false;
   if(close_move < DisplacementCloseMoveMultiplier * stats.median_range) return false;
   if(CloseLocation(rates[1]) > 0.35) return false;
   double lower_wick = MathMin(rates[1].open, rates[1].close) - rates[1].low;
   if(lower_wick > 0.50 * (rates[1].high - rates[1].low)) return false;
   return true;
}

int DetectTrendRegime(const MqlRates &rates[], const SwingInfo &swings, const MarketStats &stats, double &break_level)
{
   break_level = 0.0;
   if(!swings.has_highs || !swings.has_lows) return REGIME_UNSAFE;
   if(IsAbnormalCandle(rates[1], stats)) return REGIME_UNSAFE;

   double buffer = BosBuffer(stats);
   bool rising_lows = swings.last_low > swings.prev_low;
   bool falling_highs = swings.last_high < swings.prev_high;

   if(rising_lows && rates[1].close > swings.last_high + buffer && HasBullishDisplacement(rates, stats))
   {
      break_level = swings.last_high;
      return REGIME_TREND;
   }

   if(falling_highs && rates[1].close < swings.last_low - buffer && HasBearishDisplacement(rates, stats))
   {
      break_level = swings.last_low;
      return REGIME_TREND;
   }

   return REGIME_UNSAFE;
}

RangeInfo DetectRangeRegime(const MqlRates &rates[], const MarketStats &stats)
{
   RangeInfo r;
   r.valid = false;
   r.upper_mid = r.lower_mid = r.width = r.containment_pct = 0.0;
   r.upper_touches = r.lower_touches = 0;
   r.reason = "not_enough_structure";

   int bars = ArraySize(rates);
   int lookback = MathMin(RangeMaxBars, bars - SwingConfirmBars - 2);
   if(lookback < RangeMinBars) return r;

   double swing_highs[];
   double swing_lows[];
   int high_count = 0;
   int low_count = 0;
   ArrayResize(swing_highs, lookback);
   ArrayResize(swing_lows, lookback);

   for(int i = SwingConfirmBars + 1; i <= lookback; i++)
   {
      if(IsSwingHigh(rates, i, SwingConfirmBars))
      {
         swing_highs[high_count] = rates[i].high;
         high_count++;
      }
      if(IsSwingLow(rates, i, SwingConfirmBars))
      {
         swing_lows[low_count] = rates[i].low;
         low_count++;
      }
   }

   if(high_count < RangeTouchesPerSideMin || low_count < RangeTouchesPerSideMin)
   {
      r.reason = "touch_count_low";
      return r;
   }

   double max_high = swing_highs[0];
   double min_low = swing_lows[0];
   for(int h = 1; h < high_count; h++) max_high = MathMax(max_high, swing_highs[h]);
   for(int l = 1; l < low_count; l++) min_low = MathMin(min_low, swing_lows[l]);

   double tolerance = RangeBoundaryToleranceMedianPct * stats.median_range;
   double upper_sum = 0.0;
   double lower_sum = 0.0;
   for(int h2 = 0; h2 < high_count; h2++)
   {
      if(MathAbs(max_high - swing_highs[h2]) <= tolerance)
      {
         upper_sum += swing_highs[h2];
         r.upper_touches++;
      }
   }
   for(int l2 = 0; l2 < low_count; l2++)
   {
      if(MathAbs(swing_lows[l2] - min_low) <= tolerance)
      {
         lower_sum += swing_lows[l2];
         r.lower_touches++;
      }
   }

   if(r.upper_touches < RangeTouchesPerSideMin || r.lower_touches < RangeTouchesPerSideMin)
   {
      r.reason = "cluster_touch_count_low";
      return r;
   }

   r.upper_mid = upper_sum / r.upper_touches;
   r.lower_mid = lower_sum / r.lower_touches;
   r.width = r.upper_mid - r.lower_mid;
   if(r.width <= RangeMinWidthMedianMultiple * stats.median_range)
   {
      r.reason = "range_too_narrow";
      return r;
   }

   int contained = 0;
   int total = 0;
   double buffer = BosBuffer(stats);
   for(int c = 1; c <= lookback; c++)
   {
      if(rates[c].close >= r.lower_mid && rates[c].close <= r.upper_mid) contained++;
      if(rates[c].close > r.upper_mid + buffer || rates[c].close < r.lower_mid - buffer)
      {
         r.reason = "recent_bos_outside_range";
         return r;
      }
      total++;
   }
   r.containment_pct = (total > 0 ? 100.0 * contained / total : 0.0);
   if(r.containment_pct < RangeContainmentMinPct)
   {
      r.reason = "containment_low";
      return r;
   }

   r.valid = true;
   r.reason = "valid_range";
   return r;
}

bool IsRolloverWindow()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   int minutes = dt.hour * 60 + dt.min;
   int rollover = 21 * 60;
   return MathAbs(minutes - rollover) <= AvoidRolloverMinutes;
}

bool IsWeekendBlocked()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   if(dt.day_of_week == 6 || dt.day_of_week == 0) return true;
   if(dt.day_of_week == 5 && dt.hour >= NoTradeFridayAfterUTC) return true;
   return false;
}

bool IsNewsWindow(const string symbol)
{
   if(!UseNewsFilter) return false;
   MqlCalendarValue values[];
   datetime from_time = TradeServerFromUtc(TimeGMT() - NoTradeAfterNewsMinutes * 60);
   datetime to_time = TradeServerFromUtc(TimeGMT() + NoTradeBeforeNewsMinutes * 60);
   if(!CalendarValueHistory(values, from_time, to_time, "", "")) return false;
   int count = ArraySize(values);
   if(count <= 0) return false;

   string base = SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE);
   string profit = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);
   for(int i = 0; i < count; i++)
   {
      MqlCalendarEvent event;
      if(!CalendarEventById(values[i].event_id, event)) continue;
      if(event.importance < CALENDAR_IMPORTANCE_HIGH) continue;
      MqlCalendarCountry country;
      if(!CalendarCountryById(event.country_id, country)) continue;
      if(country.currency == base || country.currency == profit) return true;
   }
   return false;
}

double PeriodClosedProfit(const datetime utc_start)
{
   datetime server_from = TradeServerFromUtc(utc_start);
   datetime server_to = TradeServerFromUtc(TimeGMT() + 60);
   if(!HistorySelect(server_from, server_to)) return 0.0;

   double pnl = 0.0;
   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != MagicNumber) continue;
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT && entry != DEAL_ENTRY_OUT_BY) continue;
      datetime deal_utc = UtcFromTradeServer((datetime)HistoryDealGetInteger(ticket, DEAL_TIME));
      if(deal_utc < utc_start) continue;
      pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
      pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
   }
   return pnl;
}

int ConsecutiveLosses()
{
   datetime start = TradeServerFromUtc(TimeGMT() - 120 * 86400);
   datetime end = TradeServerFromUtc(TimeGMT() + 60);
   if(!HistorySelect(start, end)) return 0;
   int losses = 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != MagicNumber) continue;
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT && entry != DEAL_ENTRY_OUT_BY) continue;
      double pnl = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_COMMISSION) + HistoryDealGetDouble(ticket, DEAL_SWAP);
      if(pnl < 0.0) losses++;
      else break;
   }
   return losses;
}

int ConsecutiveRecoveryLosses()
{
   datetime start = TradeServerFromUtc(TimeGMT() - 120 * 86400);
   datetime end = TradeServerFromUtc(TimeGMT() + 60);
   if(!HistorySelect(start, end)) return 0;
   int losses = 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != MagicNumber) continue;
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT && entry != DEAL_ENTRY_OUT_BY) continue;
      string comment = HistoryDealGetString(ticket, DEAL_COMMENT);
      if(StringFind(comment, "RECOVERY") < 0) continue;
      double pnl = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_COMMISSION) + HistoryDealGetDouble(ticket, DEAL_SWAP);
      if(pnl < 0.0) losses++;
      else break;
   }
   return losses;
}

double LossPerLot(const string symbol, const double entry, const double sl)
{
   double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tick_value <= 0.0) tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(tick_size <= 0.0 || tick_value <= 0.0 || point <= 0.0) return 0.0;
   double distance = MathAbs(entry - sl);
   double price_loss = (distance / tick_size) * tick_value;
   double slippage_loss = ((EstimatedSlippagePoints * point) / tick_size) * tick_value;
   return price_loss + EstimatedCommissionRoundTurnPerLot + slippage_loss;
}

double PositionRiskMoneyByTicket(const ulong ticket)
{
   if(!PositionSelectByTicket(ticket)) return 0.0;
   string symbol = PositionGetString(POSITION_SYMBOL);
   double sl = PositionGetDouble(POSITION_SL);
   if(sl <= 0.0) return InitialCapital;
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double volume = PositionGetDouble(POSITION_VOLUME);
   return LossPerLot(symbol, open, sl) * volume;
}

double OpenRiskMoney(const string symbol_filter = "", const int family_filter = FAMILY_NONE, const string currency_filter = "")
{
   double risk = 0.0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      string symbol = PositionGetString(POSITION_SYMBOL);
      string comment = PositionGetString(POSITION_COMMENT);
      if(symbol_filter != "" && symbol != symbol_filter) continue;
      if(family_filter == FAMILY_TREND && StringFind(comment, "TREND") < 0) continue;
      if(family_filter == FAMILY_RANGE && StringFind(comment, "RANGE") < 0) continue;
      if(currency_filter != "")
      {
         string base = SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE);
         string profit = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);
         if(base != currency_filter && profit != currency_filter) continue;
      }
      risk += PositionRiskMoneyByTicket(ticket);
   }
   return risk;
}

bool HasOpenSymbolPosition(const string symbol)
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) == symbol) return true;
   }
   return false;
}

bool RecentSymbolLossCooldown(const string symbol)
{
   int seconds = PeriodSeconds(ExecutionTimeframe);
   if(seconds <= 0) seconds = 3600;
   datetime start = TradeServerFromUtc(TimeGMT() - LossCooldownBars * seconds - 3600);
   datetime end = TradeServerFromUtc(TimeGMT() + 60);
   if(!HistorySelect(start, end)) return false;

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != MagicNumber) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != symbol) continue;
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT && entry != DEAL_ENTRY_OUT_BY) continue;
      datetime deal_utc = UtcFromTradeServer((datetime)HistoryDealGetInteger(ticket, DEAL_TIME));
      if(TimeGMT() - deal_utc > LossCooldownBars * seconds) return false;
      double pnl = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_COMMISSION) + HistoryDealGetDouble(ticket, DEAL_SWAP);
      return pnl < 0.0;
   }
   return false;
}

bool AnyOpenPosition()
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) == MagicNumber) return true;
   }
   return false;
}

bool IsRecoveryActive(double &risk_pct)
{
   risk_pct = BaseRiskPct;
   if(!UseRecoveryMode) return false;
   if(AnyOpenPosition()) return false;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(balance >= InitialCapital || equity >= InitialCapital) return false;

   double deficit_pct = 100.0 * (InitialCapital - MathMin(balance, equity)) / InitialCapital;
   if(deficit_pct > RecoveryDisableDrawdownPct) return false;
   if(ConsecutiveRecoveryLosses() >= 2) return false;
   if(g_slippage_degraded) return false;

   if(deficit_pct <= 2.0) risk_pct = RecoveryL1RiskPct;
   else if(deficit_pct <= 5.0) risk_pct = RecoveryL2RiskPct;
   else risk_pct = RecoveryL3RiskPct;
   return true;
}

bool GlobalRiskGate(const string symbol, const int family, const double candidate_risk, string &reason)
{
   double daily = PeriodClosedProfit(UtcDayStart());
   double weekly = PeriodClosedProfit(UtcWeekStart());
   double monthly = PeriodClosedProfit(UtcMonthStart());
   double open_risk = OpenRiskMoney();
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   if(daily >= InitialCapital * PercentToFraction(DailyProfitTargetPct))
   {
      reason = "daily_profit_target_reached";
      return false;
   }
   if((daily < 0.0 && MathAbs(daily) + open_risk >= InitialCapital * PercentToFraction(DailyLossLimitPct)))
   {
      reason = "daily_loss_limit_reached";
      return false;
   }
   if(weekly < 0.0 && MathAbs(weekly) >= InitialCapital * PercentToFraction(WeeklyLossLimitPct))
   {
      reason = "weekly_loss_limit_reached";
      return false;
   }
   if(monthly < 0.0 && MathAbs(monthly) >= InitialCapital * PercentToFraction(MonthlyLossLimitPct))
   {
      reason = "monthly_loss_limit_reached";
      return false;
   }
   if(equity <= InitialCapital * (1.0 - PercentToFraction(MaxDrawdownPct)))
   {
      reason = "max_drawdown_stop_active";
      return false;
   }
   if(ConsecutiveLosses() >= MaxConsecutiveLosses)
   {
      reason = "consecutive_loss_stop";
      return false;
   }
   if(g_slippage_degraded)
   {
      reason = "slippage_degraded";
      return false;
   }
   if(HasOpenSymbolPosition(symbol))
   {
      reason = "symbol_locked";
      return false;
   }
   if(RecentSymbolLossCooldown(symbol))
   {
      reason = "loss_cooldown_active";
      return false;
   }

   double cap_base = InitialCapital;
   if(OpenRiskMoney(symbol) + candidate_risk > cap_base * PercentToFraction(MaxRiskPerSymbolPct))
   {
      reason = "symbol_risk_cap_exceeded";
      return false;
   }

   string base = SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE);
   string profit = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);
   if(OpenRiskMoney("", FAMILY_NONE, base) + candidate_risk > cap_base * PercentToFraction(MaxRiskPerCurrencyPct) ||
      OpenRiskMoney("", FAMILY_NONE, profit) + candidate_risk > cap_base * PercentToFraction(MaxRiskPerCurrencyPct))
   {
      reason = "currency_risk_cap_exceeded";
      return false;
   }

   if(OpenRiskMoney("", family) + candidate_risk > cap_base * PercentToFraction(MaxRiskPerStrategyPct))
   {
      reason = "strategy_family_risk_cap_exceeded";
      return false;
   }

   if(open_risk + candidate_risk > cap_base * PercentToFraction(MaxPortfolioOpenRiskPct))
   {
      reason = "portfolio_risk_cap_exceeded";
      return false;
   }

   return true;
}

bool SessionAndEventGate(const string symbol, string &reason)
{
   if(IsWeekendBlocked())
   {
      reason = "weekend_filter_active";
      return false;
   }
   if(IsRolloverWindow())
   {
      reason = "rollover_window_active";
      return false;
   }
   if(IsNewsWindow(symbol))
   {
      reason = "news_window_active";
      return false;
   }
   return true;
}

bool MarginGate(const string symbol, const int direction, const double lots, const double entry, string &reason)
{
   ENUM_ORDER_TYPE type = (direction == DIR_LONG ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double margin = 0.0;
   if(!OrderCalcMargin(type, symbol, lots, entry, margin) || margin <= 0.0)
   {
      reason = "margin_calculation_failed";
      return false;
   }

   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(free_margin - margin < margin * MinFreeMarginMultiple)
   {
      reason = "insufficient_free_margin";
      return false;
   }

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double used_after = AccountInfoDouble(ACCOUNT_MARGIN) + margin;
   if(equity > 0.0 && 100.0 * used_after / equity > MaxUsedMarginPct)
   {
      reason = "used_margin_cap_exceeded";
      return false;
   }
   return true;
}

bool StopsGate(const string symbol, const int direction, const double entry, const double sl, const double tp, string &reason)
{
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int stops_level = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   int freeze_level = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double min_distance = MathMax(stops_level, freeze_level) * point;
   if(min_distance < 0.0) min_distance = 0.0;

   if(direction == DIR_LONG)
   {
      if(sl >= entry || tp <= entry)
      {
         reason = "sl_tp_side_invalid";
         return false;
      }
   }
   else
   {
      if(sl <= entry || tp >= entry)
      {
         reason = "sl_tp_side_invalid";
         return false;
      }
   }

   if(MathAbs(entry - sl) < min_distance || MathAbs(tp - entry) < min_distance)
   {
      reason = "sl_or_tp_too_close";
      return false;
   }
   return true;
}

bool PrepareCandidate(Candidate &c, const MarketStats &stats)
{
   c.valid = false;
   MqlTick tick;
   if(!SymbolInfoTick(c.symbol, tick))
   {
      c.reason = "no_tick";
      return false;
   }
   c.entry = (c.direction == DIR_LONG ? tick.ask : tick.bid);
   c.entry = NormalizePrice(c.symbol, c.entry);
   c.sl = NormalizePrice(c.symbol, c.sl);
   c.risk_price = MathAbs(c.entry - c.sl);
   if(c.risk_price <= 0.0)
   {
      c.reason = "sl_invalid";
      return false;
   }
   c.tp = (c.direction == DIR_LONG ? c.entry + RR * c.risk_price : c.entry - RR * c.risk_price);
   c.tp = NormalizePrice(c.symbol, c.tp);

   if(MathAbs(MathAbs(c.tp - c.entry) / c.risk_price - RR) > 0.05)
   {
      c.reason = "tp_not_5r_after_rounding";
      return false;
   }

   if((stats.spread_price / c.risk_price) * 100.0 > MaxSpreadToRiskPct)
   {
      c.reason = "spread_too_high";
      return false;
   }

   double estimated_slippage_price = EstimatedSlippagePoints * stats.point;
   if((estimated_slippage_price / c.risk_price) * 100.0 > MaxSlippageToRiskPct)
   {
      c.reason = "slippage_too_high";
      return false;
   }

   string reason = "";
   if(!StopsGate(c.symbol, c.direction, c.entry, c.sl, c.tp, reason))
   {
      c.reason = reason;
      return false;
   }

   double risk_pct = BaseRiskPct;
   c.recovery = IsRecoveryActive(risk_pct);
   risk_pct = MathMin(risk_pct, MaxRiskPerTradePct);
   double risk_money = EffectiveCapital() * PercentToFraction(risk_pct);
   double loss_per_lot = LossPerLot(c.symbol, c.entry, c.sl);
   if(loss_per_lot <= 0.0)
   {
      c.reason = "loss_per_lot_invalid";
      return false;
   }

   string global_reason = "";
   if(!GlobalRiskGate(c.symbol, c.family, risk_money, global_reason))
   {
      c.reason = global_reason;
      return false;
   }

   double raw_lots = risk_money / loss_per_lot;
   if(raw_lots < SymbolInfoDouble(c.symbol, SYMBOL_VOLUME_MIN))
   {
      c.reason = "lots_below_minimum";
      return false;
   }
   c.lots = NormalizeLots(c.symbol, raw_lots);
   c.risk_money = LossPerLot(c.symbol, c.entry, c.sl) * c.lots;

   if(c.risk_money <= 0.0)
   {
      c.reason = "risk_money_invalid";
      return false;
   }
   if(!GlobalRiskGate(c.symbol, c.family, c.risk_money, global_reason))
   {
      c.reason = global_reason;
      return false;
   }

   if(!MarginGate(c.symbol, c.direction, c.lots, c.entry, reason))
   {
      c.reason = reason;
      return false;
   }

   if(!SessionAndEventGate(c.symbol, reason))
   {
      c.reason = reason;
      return false;
   }

   c.valid = true;
   c.reason = "accepted";
   return true;
}

double NearestOpposingSwing(const MqlRates &rates[], const int direction, const double entry)
{
   double level = 0.0;
   int bars = ArraySize(rates);
   int lookback = MathMin(AnalysisLookbackBars, bars - SwingConfirmBars - 1);
   for(int i = SwingConfirmBars + 1; i <= lookback; i++)
   {
      if(direction == DIR_LONG && IsSwingHigh(rates, i, SwingConfirmBars) && rates[i].high > entry)
      {
         if(level == 0.0 || rates[i].high < level) level = rates[i].high;
      }
      if(direction == DIR_SHORT && IsSwingLow(rates, i, SwingConfirmBars) && rates[i].low < entry)
      {
         if(level == 0.0 || rates[i].low > level) level = rates[i].low;
      }
   }
   return level;
}

bool TrendTargetHasRoom(const MqlRates &rates[], const Candidate &c)
{
   double opposing = NearestOpposingSwing(rates, c.direction, c.entry);
   if(opposing == 0.0) return true;
   if(c.direction == DIR_LONG && opposing < c.tp) return false;
   if(c.direction == DIR_SHORT && opposing > c.tp) return false;
   return true;
}

bool RangeTargetHasRoom(const Candidate &c, const RangeInfo &range)
{
   double danger = RangeDangerZonePct * range.width;
   if(c.direction == DIR_LONG) return c.tp < range.upper_mid - danger;
   if(c.direction == DIR_SHORT) return c.tp > range.lower_mid + danger;
   return false;
}

bool RejectionLong(const MqlRates &bar)
{
   double range = bar.high - bar.low;
   if(range <= 0.0) return false;
   double lower_wick = MathMin(bar.open, bar.close) - bar.low;
   return lower_wick / range >= RejectionWickMinPct && CloseLocation(bar) >= 0.50;
}

bool RejectionShort(const MqlRates &bar)
{
   double range = bar.high - bar.low;
   if(range <= 0.0) return false;
   double upper_wick = bar.high - MathMax(bar.open, bar.close);
   return upper_wick / range >= RejectionWickMinPct && CloseLocation(bar) <= 0.50;
}

void ClearTrendSetup(SymbolState &state)
{
   state.trend_setup_dir = DIR_NONE;
   state.trend_setup_bars_left = 0;
   state.trend_setup_stage = 0;
   state.trend_level = 0.0;
   state.trend_rejection_high = 0.0;
   state.trend_rejection_low = 0.0;
   state.trend_origin_extreme = 0.0;
}

void ClearRangeSetup(SymbolState &state)
{
   state.range_setup_dir = DIR_NONE;
   state.range_setup_bars_left = 0;
   state.range_setup_stage = 0;
   state.range_upper_mid = 0.0;
   state.range_lower_mid = 0.0;
   state.range_rejection_high = 0.0;
   state.range_rejection_low = 0.0;
   state.range_sweep_extreme = 0.0;
}

bool ExecuteCandidate(Candidate &c, const MarketStats &stats)
{
   if(!c.valid)
   {
      LogEvent("REJECT", c.symbol, FamilyName(c.family), DirectionName(c.direction), c.reason, c.entry, c.sl, c.tp, c.lots, c.risk_money, stats.spread_points);
      return false;
   }

   if(!EnableTrading)
   {
      LogEvent("DRY_RUN_ACCEPT", c.symbol, FamilyName(c.family), DirectionName(c.direction), "trading_disabled", c.entry, c.sl, c.tp, c.lots, c.risk_money, stats.spread_points);
      return false;
   }

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(MaxDeviationPoints);

   string comment = StringFormat("RSPEA:%s:%s", FamilyName(c.family), (c.recovery ? "RECOVERY" : "NORMAL"));
   bool ok = false;
   if(c.direction == DIR_LONG)
      ok = g_trade.Buy(c.lots, c.symbol, 0.0, c.sl, c.tp, comment);
   else
      ok = g_trade.Sell(c.lots, c.symbol, 0.0, c.sl, c.tp, comment);

   double fill = g_trade.ResultPrice();
   double slip = MathAbs(fill - c.entry);
   if(c.risk_price > 0.0 && (slip / c.risk_price) * 100.0 > MaxSlippageToRiskPct)
      g_slippage_degraded = true;

   string result = StringFormat("retcode_%d_%s order_%I64u deal_%I64u fill_%.8f slip_%.8f",
                                (int)g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription(),
                                g_trade.ResultOrder(), g_trade.ResultDeal(), fill, slip);

   if(ok)
      LogEvent("ORDER_SENT", c.symbol, FamilyName(c.family), DirectionName(c.direction), result, c.entry, c.sl, c.tp, c.lots, c.risk_money, stats.spread_points);
   else
      LogEvent("ORDER_FAILED", c.symbol, FamilyName(c.family), DirectionName(c.direction), result, c.entry, c.sl, c.tp, c.lots, c.risk_money, stats.spread_points);
   return ok;
}

void ProcessTrendModule(SymbolState &state, const MqlRates &rates[], const SwingInfo &swings, const MarketStats &stats, const int trend_regime, const double break_level)
{
   if(HasOpenSymbolPosition(state.symbol)) return;
   if(state.trend_setup_bars_left > 0) state.trend_setup_bars_left--;
   if(state.trend_setup_bars_left == 0 && state.trend_setup_dir != DIR_NONE) ClearTrendSetup(state);

   double buffer = BosBuffer(stats);

   if(state.trend_setup_dir == DIR_NONE && trend_regime == REGIME_TREND)
   {
      if(rates[1].close > break_level + buffer)
      {
         state.trend_setup_dir = DIR_LONG;
         state.trend_level = break_level;
         state.trend_origin_extreme = rates[1].low;
         state.trend_setup_bars_left = MaxRetestBars;
         state.trend_setup_stage = 1;
         LogEvent("SETUP", state.symbol, "TREND", "LONG", "bos_wait_retest", rates[1].close, 0, 0, 0, 0, stats.spread_points);
      }
      else if(rates[1].close < break_level - buffer)
      {
         state.trend_setup_dir = DIR_SHORT;
         state.trend_level = break_level;
         state.trend_origin_extreme = rates[1].high;
         state.trend_setup_bars_left = MaxRetestBars;
         state.trend_setup_stage = 1;
         LogEvent("SETUP", state.symbol, "TREND", "SHORT", "bos_wait_retest", rates[1].close, 0, 0, 0, 0, stats.spread_points);
      }
      return;
   }

   if(state.trend_setup_dir == DIR_LONG)
   {
      if(state.trend_setup_stage == 1 && rates[1].low <= state.trend_level + buffer && rates[1].close > state.trend_level && RejectionLong(rates[1]))
      {
         state.trend_rejection_high = rates[1].high;
         state.trend_rejection_low = MathMin(rates[1].low, state.trend_origin_extreme);
         state.trend_setup_stage = 2;
         return;
      }
      if(state.trend_setup_stage == 2 && (rates[1].high > state.trend_rejection_high || rates[1].close > state.trend_rejection_high))
      {
         Candidate c;
         c.symbol = state.symbol;
         c.direction = DIR_LONG;
         c.family = FAMILY_TREND;
         c.sl = state.trend_rejection_low - SlBuffer(stats);
         PrepareCandidate(c, stats);
         if(c.valid && !TrendTargetHasRoom(rates, c))
         {
            c.valid = false;
            c.reason = "5r_structurally_unrealistic";
         }
         ExecuteCandidate(c, stats);
         ClearTrendSetup(state);
      }
   }
   else if(state.trend_setup_dir == DIR_SHORT)
   {
      if(state.trend_setup_stage == 1 && rates[1].high >= state.trend_level - buffer && rates[1].close < state.trend_level && RejectionShort(rates[1]))
      {
         state.trend_rejection_low = rates[1].low;
         state.trend_rejection_high = MathMax(rates[1].high, state.trend_origin_extreme);
         state.trend_setup_stage = 2;
         return;
      }
      if(state.trend_setup_stage == 2 && (rates[1].low < state.trend_rejection_low || rates[1].close < state.trend_rejection_low))
      {
         Candidate c;
         c.symbol = state.symbol;
         c.direction = DIR_SHORT;
         c.family = FAMILY_TREND;
         c.sl = state.trend_rejection_high + SlBuffer(stats);
         PrepareCandidate(c, stats);
         if(c.valid && !TrendTargetHasRoom(rates, c))
         {
            c.valid = false;
            c.reason = "5r_structurally_unrealistic";
         }
         ExecuteCandidate(c, stats);
         ClearTrendSetup(state);
      }
   }
}

void ProcessRangeModule(SymbolState &state, const MqlRates &rates[], const RangeInfo &range, const MarketStats &stats)
{
   if(!range.valid || HasOpenSymbolPosition(state.symbol)) return;
   if(state.range_setup_bars_left > 0) state.range_setup_bars_left--;
   if(state.range_setup_bars_left == 0 && state.range_setup_dir != DIR_NONE) ClearRangeSetup(state);

   double buffer = BosBuffer(stats);

   if(state.range_setup_dir == DIR_NONE)
   {
      if(rates[1].low < range.lower_mid - buffer && rates[1].close > range.lower_mid && RejectionLong(rates[1]))
      {
         state.range_setup_dir = DIR_LONG;
         state.range_setup_stage = 1;
         state.range_setup_bars_left = 3;
         state.range_upper_mid = range.upper_mid;
         state.range_lower_mid = range.lower_mid;
         state.range_rejection_high = rates[1].high;
         state.range_rejection_low = rates[1].low;
         state.range_sweep_extreme = rates[1].low;
         LogEvent("SETUP", state.symbol, "RANGE", "LONG", "sweep_rejection_wait_confirm", rates[1].close, 0, 0, 0, 0, stats.spread_points);
      }
      else if(rates[1].high > range.upper_mid + buffer && rates[1].close < range.upper_mid && RejectionShort(rates[1]))
      {
         state.range_setup_dir = DIR_SHORT;
         state.range_setup_stage = 1;
         state.range_setup_bars_left = 3;
         state.range_upper_mid = range.upper_mid;
         state.range_lower_mid = range.lower_mid;
         state.range_rejection_high = rates[1].high;
         state.range_rejection_low = rates[1].low;
         state.range_sweep_extreme = rates[1].high;
         LogEvent("SETUP", state.symbol, "RANGE", "SHORT", "sweep_rejection_wait_confirm", rates[1].close, 0, 0, 0, 0, stats.spread_points);
      }
      return;
   }

   if(state.range_setup_dir == DIR_LONG && (rates[1].high > state.range_rejection_high || rates[1].close > range.lower_mid))
   {
      Candidate c;
      c.symbol = state.symbol;
      c.direction = DIR_LONG;
      c.family = FAMILY_RANGE;
      c.sl = state.range_sweep_extreme - SlBuffer(stats);
      PrepareCandidate(c, stats);
      if(c.valid && !RangeTargetHasRoom(c, range))
      {
         c.valid = false;
         c.reason = "5r_not_inside_range";
      }
      ExecuteCandidate(c, stats);
      ClearRangeSetup(state);
   }
   else if(state.range_setup_dir == DIR_SHORT && (rates[1].low < state.range_rejection_low || rates[1].close < range.upper_mid))
   {
      Candidate c;
      c.symbol = state.symbol;
      c.direction = DIR_SHORT;
      c.family = FAMILY_RANGE;
      c.sl = state.range_sweep_extreme + SlBuffer(stats);
      PrepareCandidate(c, stats);
      if(c.valid && !RangeTargetHasRoom(c, range))
      {
         c.valid = false;
         c.reason = "5r_not_inside_range";
      }
      ExecuteCandidate(c, stats);
      ClearRangeSetup(state);
   }
}

void ProcessSymbol(SymbolState &state)
{
   MqlRates rates[];
   if(!LoadRates(state.symbol, ExecutionTimeframe, AnalysisLookbackBars + SwingConfirmBars + 10, rates))
   {
      LogEvent("SKIP", state.symbol, "NONE", "NONE", "rates_unavailable");
      return;
   }

   if(state.last_bar_time == rates[0].time) return;
   state.last_bar_time = rates[0].time;

   MarketStats stats;
   if(!LoadMarketStats(state.symbol, rates, MedianLookbackBars, stats))
   {
      LogEvent("SKIP", state.symbol, "NONE", "NONE", "market_stats_invalid");
      return;
   }

   if(IsAbnormalCandle(rates[1], stats))
   {
      LogEvent("FILTER", state.symbol, "NONE", "NONE", "abnormal_candle_detected", rates[1].close, 0, 0, 0, 0, stats.spread_points);
      return;
   }

   int structure_regime = REGIME_UNSAFE;
   int structure_trend_dir = DIR_NONE;
   if(StructureTimeframe == ExecutionTimeframe)
   {
      structure_regime = REGIME_UNSAFE;
   }
   else
   {
      MqlRates structure_rates[];
      if(LoadRates(state.symbol, StructureTimeframe, AnalysisLookbackBars + SwingConfirmBars + 10, structure_rates))
      {
         MarketStats structure_stats;
         if(LoadMarketStats(state.symbol, structure_rates, MedianLookbackBars, structure_stats))
         {
            SwingInfo structure_swings = DetectSwings(structure_rates, SwingConfirmBars, AnalysisLookbackBars);
            double structure_break_level = 0.0;
            int structure_trend = DetectTrendRegime(structure_rates, structure_swings, structure_stats, structure_break_level);
            RangeInfo structure_range = DetectRangeRegime(structure_rates, structure_stats);
            if(structure_trend == REGIME_TREND)
            {
               structure_regime = REGIME_TREND;
               structure_trend_dir = (structure_rates[1].close > structure_break_level ? DIR_LONG : DIR_SHORT);
            }
            else if(structure_swings.has_highs && structure_swings.has_lows &&
                    structure_swings.last_high > structure_swings.prev_high &&
                    structure_swings.last_low > structure_swings.prev_low &&
                    !IsAbnormalCandle(structure_rates[1], structure_stats))
            {
               structure_regime = REGIME_TREND;
               structure_trend_dir = DIR_LONG;
            }
            else if(structure_swings.has_highs && structure_swings.has_lows &&
                    structure_swings.last_high < structure_swings.prev_high &&
                    structure_swings.last_low < structure_swings.prev_low &&
                    !IsAbnormalCandle(structure_rates[1], structure_stats))
            {
               structure_regime = REGIME_TREND;
               structure_trend_dir = DIR_SHORT;
            }
            else if(structure_range.valid)
            {
               structure_regime = REGIME_RANGE;
            }
         }
      }
   }

   SwingInfo swings = DetectSwings(rates, SwingConfirmBars, AnalysisLookbackBars);
   double break_level = 0.0;
   int trend_regime = DetectTrendRegime(rates, swings, stats, break_level);
   int execution_trend_dir = (trend_regime == REGIME_TREND ? (rates[1].close > break_level ? DIR_LONG : DIR_SHORT) : DIR_NONE);
   RangeInfo range = DetectRangeRegime(rates, stats);
   int regime = (trend_regime == REGIME_TREND ? REGIME_TREND : (range.valid ? REGIME_RANGE : REGIME_UNSAFE));

   if(StructureTimeframe != ExecutionTimeframe)
   {
      if(structure_regime == REGIME_TREND && regime == REGIME_TREND && structure_trend_dir == execution_trend_dir)
      {
         regime = REGIME_TREND;
      }
      else if(structure_regime == REGIME_RANGE && regime == REGIME_RANGE)
      {
         regime = REGIME_RANGE;
      }
      else
      {
         regime = REGIME_UNSAFE;
      }
   }

   LogEvent("REGIME", state.symbol, RegimeName(regime), "NONE", (regime == REGIME_RANGE ? range.reason : "evaluated"),
            rates[1].close, 0, 0, 0, 0, stats.spread_points);

   if(regime == REGIME_TREND)
   {
      ClearRangeSetup(state);
      ProcessTrendModule(state, rates, swings, stats, trend_regime, break_level);
   }
   else if(regime == REGIME_RANGE)
   {
      ClearTrendSetup(state);
      ProcessRangeModule(state, rates, range, stats);
   }
   else
   {
      ClearTrendSetup(state);
      ClearRangeSetup(state);
   }
}

double RecentMinorSwingLevel(const string symbol, const int direction)
{
   MqlRates rates[];
   if(!LoadRates(symbol, ExecutionTimeframe, 80, rates)) return 0.0;
   int bars = ArraySize(rates);
   int lookback = MathMin(60, bars - MinorSwingBars - 1);
   for(int i = MinorSwingBars + 1; i <= lookback; i++)
   {
      if(direction == DIR_LONG && IsSwingLow(rates, i, MinorSwingBars)) return rates[i].low;
      if(direction == DIR_SHORT && IsSwingHigh(rates, i, MinorSwingBars)) return rates[i].high;
   }
   return 0.0;
}

void ManagePositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      if((long)PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      string comment = PositionGetString(POSITION_COMMENT);
      int type = (int)PositionGetInteger(POSITION_TYPE);
      int direction = (type == POSITION_TYPE_BUY ? DIR_LONG : DIR_SHORT);
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      if(sl <= 0.0 || tp <= 0.0) continue;

      MqlTick tick;
      if(!SymbolInfoTick(symbol, tick)) continue;
      MarketStats stats;
      MqlRates rates[];
      if(!LoadRates(symbol, ExecutionTimeframe, AnalysisLookbackBars + 10, rates)) continue;
      if(!LoadMarketStats(symbol, rates, MedianLookbackBars, stats)) continue;

      double price = (direction == DIR_LONG ? tick.bid : tick.ask);
      double original_r = MathAbs(tp - entry) / RR;
      if(original_r <= 0.0) continue;
      double open_r = (direction == DIR_LONG ? price - entry : entry - price) / original_r;
      double new_sl = sl;

      if(UseBreakEven && open_r >= BreakEvenAfterR)
      {
         double cost_buffer = stats.spread_price + EstimatedSlippagePoints * stats.point;
         double be = (direction == DIR_LONG ? entry + cost_buffer : entry - cost_buffer);
         if(direction == DIR_LONG && sl < be) new_sl = MathMax(new_sl, be);
         if(direction == DIR_SHORT && sl > be) new_sl = MathMin(new_sl, be);
      }

      double trail_after = (StringFind(comment, "RANGE") >= 0 ? TrailAfterRangeR : TrailAfterTrendR);
      if(UseStructureTrailing && open_r >= trail_after)
      {
         double swing = RecentMinorSwingLevel(symbol, direction);
         double buffer = SlBuffer(stats);
         if(direction == DIR_LONG && swing > 0.0)
         {
            double structural_sl = swing - buffer;
            if(structural_sl > new_sl && structural_sl < price) new_sl = structural_sl;
         }
         else if(direction == DIR_SHORT && swing > 0.0)
         {
            double structural_sl = swing + buffer;
            if(structural_sl < new_sl && structural_sl > price) new_sl = structural_sl;
         }
      }

      if(open_r >= LockOneRAfterR)
      {
         double lock = (direction == DIR_LONG ? entry + original_r : entry - original_r);
         if(direction == DIR_LONG && new_sl < lock) new_sl = lock;
         if(direction == DIR_SHORT && new_sl > lock) new_sl = lock;
      }

      new_sl = NormalizePrice(symbol, new_sl);
      if(MathAbs(new_sl - sl) < stats.point) continue;

      string reason = "";
      if(!StopsGate(symbol, direction, price, new_sl, tp, reason)) continue;
      if(EnableTrading)
      {
         if(g_trade.PositionModify(ticket, new_sl, tp))
            LogEvent("MODIFY_SL", symbol, (StringFind(comment, "RANGE") >= 0 ? "RANGE" : "TREND"), DirectionName(direction), "structure_management", price, new_sl, tp, PositionGetDouble(POSITION_VOLUME), 0, stats.spread_points);
         else
            LogEvent("MODIFY_FAILED", symbol, (StringFind(comment, "RANGE") >= 0 ? "RANGE" : "TREND"), DirectionName(direction), g_trade.ResultRetcodeDescription(), price, new_sl, tp, PositionGetDouble(POSITION_VOLUME), 0, stats.spread_points);
      }
      else
      {
         LogEvent("DRY_RUN_MODIFY", symbol, (StringFind(comment, "RANGE") >= 0 ? "RANGE" : "TREND"), DirectionName(direction), "trading_disabled", price, new_sl, tp, PositionGetDouble(POSITION_VOLUME), 0, stats.spread_points);
      }
   }
}

void ParseSymbols()
{
   string parts[];
   int count = StringSplit(SymbolsWhitelist, ',', parts);
   ArrayResize(g_symbols, 0);
   ArrayResize(g_states, 0);
   for(int i = 0; i < count; i++)
   {
      string sym = TrimString(parts[i]);
      if(sym == "") continue;
      if(!SymbolSelect(sym, true))
      {
         Print("Could not select symbol: ", sym);
         continue;
      }
      int n = ArraySize(g_symbols);
      ArrayResize(g_symbols, n + 1);
      ArrayResize(g_states, n + 1);
      g_symbols[n] = sym;
      g_states[n].symbol = sym;
      g_states[n].last_bar_time = 0;
      g_states[n].cooldown_until_bar = 0;
      ClearTrendSetup(g_states[n]);
      ClearRangeSetup(g_states[n]);
   }
}

int OnInit()
{
   if(RR < 4.99 || RR > 5.01)
   {
      Print("RR must remain 5.0 for the default production rules.");
      return INIT_PARAMETERS_INCORRECT;
   }

   ParseSymbols();
   if(ArraySize(g_symbols) == 0)
   {
      Print("No valid symbols selected.");
      return INIT_FAILED;
   }

   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints(MaxDeviationPoints);

   if(WriteCsvLog)
   {
      g_log_handle = FileOpen(CsvLogFileName, FILE_COMMON|FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ|FILE_SHARE_WRITE);
      if(g_log_handle != INVALID_HANDLE)
      {
         if(FileSize(g_log_handle) == 0)
            FileWrite(g_log_handle, "utc_time", "event", "symbol", "family", "direction", "reason", "entry", "sl", "tp", "lots", "risk_money", "spread_points");
         FileSeek(g_log_handle, 0, SEEK_END);
      }
      else
      {
         Print("CSV log open failed: ", GetLastError());
      }
   }

   EventSetTimer(10);
   Print("RawStructurePortfolioEA initialized. Symbols=", ArraySize(g_symbols), " EnableTrading=", EnableTrading, " Magic=", MagicNumber);
   if(!EnableTrading) Print("Trading is disabled. EA will log DRY_RUN_ACCEPT instead of placing orders.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(g_log_handle != INVALID_HANDLE)
   {
      FileFlush(g_log_handle);
      FileClose(g_log_handle);
      g_log_handle = INVALID_HANDLE;
   }
}

void ProcessAllSymbols()
{
   for(int i = 0; i < ArraySize(g_states); i++)
      ProcessSymbol(g_states[i]);
}

void OnTick()
{
   ManagePositions();
}

void OnTimer()
{
   ProcessAllSymbols();
   ManagePositions();
}
