//+------------------------------------------------------------------+
//| ListTwoEdgeSymbols.mq5                                           |
//| Prints broker symbol names that match the requested base pairs.   |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

bool ContainsPair(const string symbol, const string pair)
{
   string upper_symbol = symbol;
   string upper_pair = pair;
   StringToUpper(upper_symbol);
   StringToUpper(upper_pair);
   return (StringFind(upper_symbol, upper_pair) >= 0);
}

void OnStart()
{
   string pairs[3] = {"EURUSD", "USDJPY", "EURGBP"};
   int total = SymbolsTotal(false);
   Print("ListTwoEdgeSymbols total=", total);

   for(int p = 0; p < 3; p++)
   {
      int found = 0;
      for(int i = 0; i < total; i++)
      {
         string name = SymbolName(i, false);
         if(ContainsPair(name, pairs[p]))
         {
            found++;
            Print("ListTwoEdgeSymbols pair=", pairs[p], " symbol=", name,
                  " selected=", SymbolInfoInteger(name, SYMBOL_SELECT),
                  " visible=", SymbolInfoInteger(name, SYMBOL_VISIBLE));
         }
      }
      if(found == 0)
         Print("ListTwoEdgeSymbols pair=", pairs[p], " symbol=<none>");
   }
}
