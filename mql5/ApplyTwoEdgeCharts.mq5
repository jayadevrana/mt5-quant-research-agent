//+------------------------------------------------------------------+
//| ApplyTwoEdgeCharts.mq5                                           |
//| Opens H1 charts and applies both TwoEdge EA templates.            |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

string ResolveSymbol(const string requested)
{
   if(SymbolSelect(requested, true))
      return requested;

   string needle = requested;
   StringToUpper(needle);
   int total = SymbolsTotal(false);
   for(int idx = 0; idx < total; idx++)
   {
      string candidate = SymbolName(idx, false);
      string upper_candidate = candidate;
      StringToUpper(upper_candidate);
      if(StringFind(upper_candidate, needle) >= 0)
      {
         if(SymbolSelect(candidate, true))
            return candidate;
      }
   }

   return requested;
}

bool OpenAndApply(const string requested_symbol, const string expert_prefix)
{
   string symbol = ResolveSymbol(requested_symbol);
   string template_name = expert_prefix + "_" + symbol + "_H1.tpl";
   bool selected = false;
   for(int attempt = 0; attempt < 30; attempt++)
   {
      ResetLastError();
      if(SymbolSelect(symbol, true))
      {
         selected = true;
         break;
      }
      Sleep(1000);
   }

   if(!selected)
   {
      Print("ApplyTwoEdgeCharts SymbolSelect failed, attempting ChartOpen anyway: ",
            symbol, " err=", GetLastError());
      int total = SymbolsTotal(false);
      string needle = requested_symbol;
      StringToUpper(needle);
      for(int idx = 0; idx < total; idx++)
      {
         string candidate = SymbolName(idx, false);
         string upper_candidate = candidate;
         StringToUpper(upper_candidate);
         if(StringFind(upper_candidate, needle) >= 0 ||
            (requested_symbol == "EURGBP" && StringFind(upper_candidate, "EUR") >= 0 && StringFind(upper_candidate, "GBP") >= 0))
         {
            Print("ApplyTwoEdgeCharts candidate for ", requested_symbol, ": ", candidate,
                  " select=", SymbolInfoInteger(candidate, SYMBOL_SELECT),
                  " visible=", SymbolInfoInteger(candidate, SYMBOL_VISIBLE));
         }
      }
   }

   long chart_id = ChartOpen(symbol, PERIOD_H1);
   if(chart_id <= 0)
   {
      Print("ApplyTwoEdgeCharts ChartOpen failed: ", symbol, " err=", GetLastError());
      return false;
   }

   Sleep(1200);
   ChartSetSymbolPeriod(chart_id, symbol, PERIOD_H1);
   Sleep(800);
   bool ok = ChartApplyTemplate(chart_id, template_name);
   Print("ApplyTwoEdgeCharts symbol=", symbol, " chart=", chart_id,
         " template=", template_name, " ok=", ok, " err=", GetLastError());
   return ok;
}

void OnStart()
{
   string symbols[3] = {"EURUSD", "USDJPY", "EURGBP"};
   for(int i = 0; i < 3; i++)
   {
      OpenAndApply(symbols[i], "TwoEdge_EA1_Trend");
      OpenAndApply(symbols[i], "TwoEdge_EA2_RangeBreakFade");
   }
}
