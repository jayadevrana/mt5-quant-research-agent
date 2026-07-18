//+------------------------------------------------------------------+
//| SaveRawStructureTemplate.mq5                                     |
//| Saves the current chart template after startup EA attachment.     |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

input string TemplatePrefix = "RawStructurePortfolioEA";

void OnStart()
{
   string symbol = ChartSymbol(0);
   ENUM_TIMEFRAMES period = (ENUM_TIMEFRAMES)ChartPeriod(0);
   string period_name = EnumToString(period);
   StringReplace(period_name, "PERIOD_", "");
   string template_name = TemplatePrefix + "_" + symbol + "_" + period_name + ".tpl";

   Sleep(3000);
   bool ok = ChartSaveTemplate(0, template_name);
   Print("SaveRawStructureTemplate symbol=", symbol, " period=", period_name,
         " template=", template_name, " ok=", ok, " err=", GetLastError());
}
