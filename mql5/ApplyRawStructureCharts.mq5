//+------------------------------------------------------------------+
//| ApplyRawStructureCharts.mq5                                      |
//| Opens H1 charts and applies saved RawStructure EA templates.      |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

input bool ApplyEURUSD = true;
input bool ApplyUSDJPY = true;
input bool ApplyEURGBP = true;

bool OpenAndApply(const string symbol)
{
   if(!SymbolSelect(symbol, true))
   {
      Print("ApplyRawStructureCharts SymbolSelect failed: ", symbol, " err=", GetLastError());
      return false;
   }

   long chart_id = ChartOpen(symbol, PERIOD_H1);
   if(chart_id <= 0)
   {
      Print("ApplyRawStructureCharts ChartOpen failed: ", symbol, " err=", GetLastError());
      return false;
   }

   Sleep(1500);
   ChartSetSymbolPeriod(chart_id, symbol, PERIOD_H1);
   Sleep(1000);

   string template_name = "RawStructurePortfolioEA_" + symbol + "_H1.tpl";
   bool ok = ChartApplyTemplate(chart_id, template_name);
   Print("ApplyRawStructureCharts symbol=", symbol, " chart=", chart_id,
         " template=", template_name, " ok=", ok, " err=", GetLastError());
   return ok;
}

void OnStart()
{
   if(ApplyEURUSD) OpenAndApply("EURUSD");
   if(ApplyUSDJPY) OpenAndApply("USDJPY");
   if(ApplyEURGBP) OpenAndApply("EURGBP");
}
