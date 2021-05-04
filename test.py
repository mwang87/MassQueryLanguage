import msql_parser
import msql_engine

raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271 AND MS2PREC=500 AND MS1MZ=100"
#raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271:MZDELTA=0.01:INTENSITYPERCENT>10 AND MS2PREC=500"
#raw = "QUERY scanrangesum(MS1DATA, TOLERANCE=0.1) WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2PROD=85.02820:MZDELTA=0.01 AND MS2NL=59.07350:MZDELTA=0.01):MZDELTA=0.01"
# statements = sqlparse.split(raw)

# print(statements)

# first = statements[0]

# print(sqlparse.format(first, reindent=True, keyword_case='upper'))

# parsed = sqlparse.parse(raw)[0]
# for token in parsed.tokens:
#     print("X", token)

parsed_output = msql_parser.parse_msql(raw)
print(parsed_output)

results = msql_engine.process_query(raw, "test/GNPS00002_A3_p.mzML")