//+------------------------------------------------------------------+
//| SaveTwoEdgeRangeTemplate.mq5                                     |
//| Saves the current chart template after EA-2 startup attachment.   |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

void OnStart()
{
   string symbol = ChartSymbol(0);
   string template_name = "TwoEdge_EA2_RangeBreakFade_" + symbol + "_H1.tpl";
   Sleep(3000);
   bool ok = ChartSaveTemplate(0, template_name);
   Print("SaveTwoEdgeRangeTemplate symbol=", symbol,
         " template=", template_name, " ok=", ok, " err=", GetLastError());
}
