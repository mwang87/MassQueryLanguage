import os

from lark import Lark
from lark import Transformer
from lark import tree

from py_expression_eval import Parser
math_parser = Parser()

from pyteomics import mass



#TODO: Update language definition to make it such that we can distinguish different functions

class MassQLToJSON(Transformer):
   def wherekeyword(self, items):
      return "WHERE"

   def querykeyword(self, items):
      return "QUERY"

   def booleanandconjunction(self, s):
      return "AND"

   def booleanorconjunction(self, s):
      return "OR"

   def qualifiermztolerance(self, items):
      return "qualifiermztolerance"
   
   def qualifierppmtolerance(self, items):
      return "qualifierppmtolerance"

   def qualifierintensityvalue(self, items):
      return "qualifierintensityvalue"

   def qualifierintensitypercent(self, items):
      return "qualifierintensitypercent"

   def qualifierintensityticpercent(self, items):
      return "qualifierintensityticpercent"

   def qualifierintensitymatch(self, items):
      return "qualifierintensitymatch"

   def qualifierintensitytolpercent(self, items):
      return "qualifierintensitytolpercent"

   def qualifierintensityreference(self, items):
      return "qualifierintensityreference"

   def ms2productcondition(self, items):
      return "ms2productcondition"

   def ms2precursorcondition(self, items):
      return "ms2precursorcondition"

   def ms2neutrallosscondition(self, items):
      return "ms2neutrallosscondition"
   
   def ms1mzcondition(self, items):
      return "ms1mzcondition"
   
   def rtmincondition(self, items):
      return "rtmincondition"

   def rtmaxcondition(self, items):
      return "rtmaxcondition"

   def scanmincondition(self, items):
      return "scanmincondition"

   def scanmaxcondition(self, items):
      return "scanmaxcondition"

   def chargecondition(self, items):
      return "chargecondition"

   def polaritycondition(self, items):
      return "polaritycondition"

   def positivepolarity(self, items):
      return "positivepolarity"

   def negativepolarity(self, items):
      return "negativepolarity"

   def xcondition(self, items):
      return "xcondition"

   def xfunction(self, items):
      return items[0]
   
   def xrange(self, items):
      return "xrange"
   
   def xdefect(self, items):
      return "xdefect"

   def qualifier(self, items):
      if len(items) == 1 and items[0] == "qualifierintensityreference":
         qualifier_type = items[0]
         
         qualifier_dict = {}
         qualifier_dict["type"] = "qualifier"
         qualifier_dict[qualifier_type] = {}
         qualifier_dict[qualifier_type]["name"] = qualifier_type

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

         if qualifier_dict[qualifier_type]["name"] == "qualifierintensitymatch":
            # NOTE: these matches should contain variables that the engine will understand
            qualifier_dict[qualifier_type]["value"] = items[-1]
         else:
            qualifier_dict[qualifier_type]["value"] = float(items[-1])

      # We are at a merge node for the qualifier
      if len(items) == 2:
         qualifier_dict = {}
         
         for qualifier in items:
            for key in qualifier:
               qualifier_dict[key] = qualifier[key]

      return qualifier_dict

   def conditionfields(self, items):
      return items[0]

   def condition(self, items):
      condition_type = items[0]

      if len(items) == 2:
         # These are most queries, with a numericalexpression
         condition_dict = {}
         condition_dict["type"] = condition_type
         condition_dict["value"] = [items[-1]]
      elif len(items) == 3:
         # These are for polarity or numerical expression
         if condition_type == "polaritycondition":
            condition_dict = {}
            condition_dict["type"] = items[0]
            condition_dict["value"] = [items[-1]]
         else:
            # These are numerical expressions for mz,rt type conditions
            condition_dict = {}
            condition_dict["type"] = items[0]
            condition_dict["value"] = items[-1]
      elif len(items) == 5:
         # These are for the x range clauses
         if items[0] == "xcondition":
            function = items[2]

            condition_dict = {}
            condition_dict["type"] = condition_type

            if function == "xdefect":
               condition_dict["mindefect"] = float(items[-2])
               condition_dict["maxdefect"] = float(items[-1])
            elif function == "xrange":
               condition_dict["min"] = float(items[-2])
               condition_dict["max"] = float(items[-1])
   
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
      items = [item for item in items if item != "WHERE"]
      items = [item for item in items if item != "QUERY"]

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

   # Handling Numerical Expressions
   def plus(self, s):
      return "+"
   def multiply(self, s):
      return "*"
   def minus(self, s):
      return "-"
   def divide(self, s):
      return "/"

   def factor(self, s):
      return s[0]

   def term(self, items):
      if len(items) == 1:
         return items[0]

      has_variable = _has_variable(items)

      string_items = [str(item) for item in items]
      full_expression = "".join(string_items)

      if has_variable:
         return full_expression

      calculated_value = math_parser.parse(full_expression).evaluate({})
      
      return calculated_value

   def numericalexpression(self, items):
      if len(items) == 1:
         return items[0]

      has_variable = _has_variable(items)

      string_items = [str(item) for item in items]
      full_expression = "".join(string_items)

      if has_variable:
         return full_expression

      # Calculating the expression
      calculated_value = math_parser.parse(full_expression).evaluate({})
      
      return calculated_value

   def numericalexpressionwithor(self, items):
      if len(items) == 1:
         return items[0]
            
      # Lets merge these values, based upon type
      merged_list = []

      if isinstance(items[0], list):
         merged_list += items[0]
      else:
         merged_list.append(items[0])
      
      if isinstance(items[-1], list):
         merged_list += items[-1]
      else:
         merged_list.append(items[-1])
         
      return merged_list
    
   def moleculeformula(self, items):
      exact_mass = mass.calculate_mass(formula=items[0])

      return exact_mass

   def aminoacids(self, items):
      exact_mass = mass.calculate_mass(sequence=items[0])
      exact_mass = exact_mass - mass.calculate_mass(formula="H2O")
      return exact_mass

   def peptide(self, items):
      return items[0]

   def peptidecharge(self, items):
      return items[0]

   def peptideion(self, items):
      return items[0]

   def peptidefunction(self, items):
      exact_mass = mass.calculate_mass(sequence=items[0], ion_type=items[2].lower(), charge=int(items[1]))
      return exact_mass
   


   def string(self, s):
      (s,) = s
      return s[1:-1]
      
   def floating(self, n):
      (n,) = n
      return float(n)


def _has_variable(items):
   acceptable_variables = ["X", "Y"]

   for item in items:
      for variable in acceptable_variables:
         if variable in str(item):
            return True

   return False 

def _visualize_parse(input_query, path_to_grammar=None, output_filename="parse.png"):
   if path_to_grammar is None:
      path_to_grammar = os.path.join(os.path.dirname(__file__), "msql.ebnf")

   msql_parser = Lark(open(path_to_grammar).read(), start='statement')
   parsed_tree = msql_parser.parse(input_query)
   tree.pydot__tree_to_png(parsed_tree, output_filename)

def parse_msql(input_query, path_to_grammar=None):
   if path_to_grammar is None:
      path_to_grammar = os.path.join(os.path.dirname(__file__), "msql.ebnf")

   # NOTE: Force capitalization on the input_query, turning this off due to needing lower case in formulas
   # input_query = input_query.upper()

   # Lets try to strip off any comments
   query_splits = input_query.split("\n")
   query_splits = [split.lstrip() for split in query_splits]
   query_splits = [split for split in query_splits if len(split) > 0]
   query_splits = [split.split("#")[0] for split in query_splits]
   query_splits = [split.lstrip() for split in query_splits]
   query_splits = [split for split in query_splits if len(split) > 0]

   input_query = "\n".join(query_splits)

   msql_parser = Lark(open(path_to_grammar).read(), start='statement')
   parsed_tree = msql_parser.parse(input_query)
   parsed_list = MassQLToJSON().transform(parsed_tree)

   parsed_list["query"] = input_query

   return parsed_list
