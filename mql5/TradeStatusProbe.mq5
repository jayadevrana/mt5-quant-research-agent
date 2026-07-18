//+------------------------------------------------------------------+
//| TradeStatusProbe.mq5                                             |
//| Prints account, terminal, position, order, and symbol status.      |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

input string ProbeSymbols = "EURUSD,USDJPY,EURGBP,EURGBP+";

string Trim(const string value)
{
   string out = value;
   StringTrimLeft(out);
   StringTrimRight(out);
   return out;
}

void PrintSymbolStatus(const string symbol)
{
   string sym = Trim(symbol);
   if(sym == "")
      return;

   ResetLastError();
   bool selected = SymbolSelect(sym, true);
   int err = GetLastError();
   MqlTick tick;
   bool tick_ok = SymbolInfoTick(sym, tick);
   PrintFormat("PROBE_SYMBOL symbol=%s selected=%s err=%d tick_ok=%s bid=%.8f ask=%.8f spread_points=%.1f trade_mode=%d point=%.8f tick_value=%.5f vol_min=%.2f vol_step=%.2f",
               sym, selected ? "true" : "false", err, tick_ok ? "true" : "false",
               tick.bid, tick.ask,
               SymbolInfoDouble(sym, SYMBOL_POINT) > 0.0 ? (tick.ask - tick.bid) / SymbolInfoDouble(sym, SYMBOL_POINT) : 0.0,
               (int)SymbolInfoInteger(sym, SYMBOL_TRADE_MODE),
               SymbolInfoDouble(sym, SYMBOL_POINT),
               SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE),
               SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP));
}

void OnStart()
{
   PrintFormat("PROBE_ACCOUNT login=%I64d server=%s company=%s trade_allowed=%s trade_expert=%s trade_mode=%d balance=%.2f equity=%.2f margin_free=%.2f",
               AccountInfoInteger(ACCOUNT_LOGIN),
               AccountInfoString(ACCOUNT_SERVER),
               AccountInfoString(ACCOUNT_COMPANY),
               AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) ? "true" : "false",
               AccountInfoInteger(ACCOUNT_TRADE_EXPERT) ? "true" : "false",
               (int)AccountInfoInteger(ACCOUNT_TRADE_MODE),
               AccountInfoDouble(ACCOUNT_BALANCE),
               AccountInfoDouble(ACCOUNT_EQUITY),
               AccountInfoDouble(ACCOUNT_MARGIN_FREE));

   PrintFormat("PROBE_TERMINAL trade_allowed=%s connected=%s mql_trade_allowed=%s positions=%d orders=%d",
               TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "true" : "false",
               TerminalInfoInteger(TERMINAL_CONNECTED) ? "true" : "false",
               MQLInfoInteger(MQL_TRADE_ALLOWED) ? "true" : "false",
               PositionsTotal(),
               OrdersTotal());

   string parts[];
   int n = StringSplit(ProbeSymbols, ',', parts);
   for(int i = 0; i < n; i++)
      PrintSymbolStatus(parts[i]);
}
