
from lark import Lark
from lark import Transformer


#TODO: Update language definition to make it such that we can distinguish different functions

class MassQLToJSON(Transformer):
   def qualifiermztolerance(self, items):
      return "qualifiermztolerance"
   
   def qualifierppmtolerance(self, items):
      return "qualifierppmtolerance"

   def qualifierintensityvalue(self, items):
      return "qualifierintensityvalue"

   def qualifierintensitypercent(self, items):
      return "qualifierintensitypercent"

   def ms2productcondition(self, items):
      return "ms2productcondition"

   def ms2precursorcondition(self, items):
      return "ms2precursorcondition"

   def ms2neutrallosscondition(self, items):
      return "ms2neutrallosscondition"
   
   def ms1mzcondition(self, items):
      return "ms1mzcondition"

   def qualifier(self, items):

      # We are at a qualifier leaf
      if len(items) == 3:
         qualifier_type = items[0]

         qualifier_dict = {}
         qualifier_dict["type"] = "qualifier"
         qualifier_dict[qualifier_type] = {}
         qualifier_dict[qualifier_type]["name"] = qualifier_type

         if qualifier_type == "qualifierppmtolerance":
            qualifier_dict[qualifier_type]["unit"] = "ppm"
         if qualifier_type == "qualifiermztolerance":
            qualifier_dict[qualifier_type]["unit"] = "mz"

         qualifier_dict[qualifier_type]["value"] = items[-1]

      # We are at a merge node for the qualifier
      if len(items) == 2:
         qualifier_dict = {}
         
         for qualifier in items:
            for key in qualifier:
               qualifier_dict[key] = qualifier[key]

      return qualifier_dict

   def condition(self, items):
      condition_dict = {}
      condition_dict["type"] = items[0].children[0]
      condition_dict["value"] = [items[1]]
      return condition_dict

   def wherefullcondition(self, items):
      """
      Defines the full set of qualifiers for a single constraint or all constraints

      Args:
          items ([type]): [description]

      Returns:
          [type]: [description]
      """

      # Only condition, no qualifiers
      if len(items) == 1:
         items[0]["conditiontype"] = "where"
         return items
      
      # Has potentially a qualifier
      if len(items) == 2:
         if items[1]["type"] == "qualifier":
            condition_dict = items[0]
            condition_dict["conditiontype"] = "where"
            condition_dict["qualifiers"] = items[1]

            return [condition_dict]
         else:
            raise Exception

      # Merging two conditions
      if len(items) == 3:
         merged_list = []
         merged_list += items[0]
         merged_list += items[-1]

         return merged_list

   def filterfullcondition(self, items):
      """
      Defines the full set of qualifiers for a single constraint or all constraints

      Args:
          items ([type]): [description]

      Returns:
          [type]: [description]
      """

      # Only condition, no qualifiers
      if len(items) == 1:
         items[0]["conditiontype"] = "filter"
         return items
      
      # Has potentially a qualifier
      if len(items) == 2:
         if items[1]["type"] == "qualifier":
            condition_dict = items[0]
            condition_dict["conditiontype"] = "filter"
            condition_dict["qualifiers"] = items[1]

            return [condition_dict]
         else:
            raise Exception

      # Merging two conditions
      if len(items) == 3:
         merged_list = []
         merged_list += items[0]
         merged_list += items[-1]

         return merged_list

   
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
      print(len(items))

      if len(items) == 1:
         query_dict = {}
         query_dict["querytype"] = items[0]
         query_dict["conditions"] = []

      if len(items) == 2:
         query_dict = {}
         query_dict["querytype"] = items[0]
         query_dict["conditions"] = items[1]
      
      if len(items) == 3:
         query_dict = {}
         query_dict["querytype"] = items[0]
         query_dict["conditions"] = items[1] + items[2]

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
