
from lark import Lark
from lark import Transformer


#TODO: Update language definition to make it such that we can distinguish different functions

class MassQLToJSON(Transformer):
   def qualifiermztolerance(self, items):
      return "qualifiermztolerance"
   
   def qualifierppmtolerance(self, items):
      return "qualifierppmtolerance"

   def ms2productcondition(self, items):
      return "ms2productcondition"

   def ms2precursorcondition(self, items):
      return "ms2precursorcondition"

   def ms2neutrallosscondition(self, items):
      return "ms2neutrallosscondition"
   
   def ms1mzcondition(self, items):
      return "ms1mzcondition"

   def qualifier(self, items):
      tolerance_type = items[0]

      qualifier_dict = {}
      qualifier_dict["type"] = "qualifier"
      qualifier_dict["field"] = items[0]
      if tolerance_type == "qualifierppmtolerance":
         qualifier_dict["unit"] = "ppm"
      else:
         qualifier_dict["unit"] = "mz"
      qualifier_dict["value"] = items[-1]
      return qualifier_dict

   def condition(self, items):
      condition_dict = {}
      condition_dict["type"] = items[0].children[0]
      condition_dict["value"] = items[1]
      return condition_dict

   def fullcondition(self, items):
      """
      Defines the full set of qualifiers for a single constraint or all constraints

      Args:
          items ([type]): [description]

      Returns:
          [type]: [description]
      """
      if len(items) == 1:
         return items
      
      if len(items) == 2:
         return items

      full_items_list = []
      for item in items:
         try:
            full_items_list += item
         except TypeError:
            pass

      return full_items_list
   
   def querytype(self, items):
      query_dict = {}
      if len(items) == 1:
         query_dict["function"] = None
         query_dict["datatype"] = items[0].data
      else:
         query_dict["function"] = items[0].data
         query_dict["datatype"] = items[1].data

      return query_dict

   def function(self, items):
      return items[0]
   
   def statement(self, items):
      if len(items) == 1:
         query_dict = {}
         query_dict["querytype"] = items[0]
         query_dict["conditions"] = []
      else:
         query_dict = {}
         query_dict["querytype"] = items[0]
         query_dict["conditions"] = items[1]
      
      return query_dict

   def qualifierfields(self, items):
      return items[0]

   def variable(self, s):
      return s[0].value

   def string(self, s):
      (s,) = s
      return s[1:-1]
      
   def floating(self, n):
      (n,) = n
      return float(n)


def parse_msql(input_query):
   msql_parser = Lark(open("msql.ebnf").read(), start='statement')
   tree = msql_parser.parse(input_query)
   parsed_list = MassQLToJSON().transform(tree)

   return parsed_list
