import msql_parser
import msql_engine

def test_simple_ms2():
    query = "QUERY MS2DATA WHERE MS2PROD=226.18"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")

def test_simple_ms2_qualifier():
    query = "QUERY MS2DATA WHERE MS2PROD=226.18:PPMDELTA=5"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")

def test_simple_ms1():
    query = "QUERY MS1DATA WHERE MS2PROD=226.18"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_qc_ms1_ms2peak():
    query = "QUERY MS1DATA WHERE MS2PROD=156.01"
    results_df = msql_engine.process_query(query, "test/QC_0.mzML")
    print(set(results_df["scan"]))

def test_diphen():
    #query = "QUERY scannum(MS2DATA) WHERE MS2PROD=167.0857:PPMDELTA=5"
    query = "QUERY scannum(MS2DATA) WHERE MS2PROD=167.0857"
    print(msql_parser.parse_msql(query))
    results_df = msql_engine.process_query(query, "test/bld_plt1_07_120_1.mzML")
    assert(1235 in list(results_df["scan"]))
    assert(1316 in list(results_df["scan"]))
    assert(1293 in list(results_df["scan"]))

def test_diphen_nl():
    query = "QUERY scannum(MS2DATA) WHERE MS2NL=176.0321"
    print(msql_parser.parse_msql(query))
    results_df = msql_engine.process_query(query, "test/bld_plt1_07_120_1.mzML")
    assert(1237 in list(results_df["scan"]))
    print(set(results_df["scan"]))

def test_diphen_combo():
    # TODO: this is a bug
    query = "QUERY scannum(MS2DATA) WHERE MS2NL=176.0321 AND MS2PROD=85.02915"
    print(msql_parser.parse_msql(query))
    results_df = msql_engine.process_query(query, "test/bld_plt1_07_120_1.mzML")
    assert(1237 in list(results_df["scan"]))
    print(set(results_df["scan"]))

def main():
    #test_simple_ms2_qualifier()
    #test_diphen()
    #test_diphen_nl()
    test_diphen_combo()

if __name__ == "__main__":
    main()

# raw = "QUERY MS2DATA WHERE MS2PROD=226.18"
# #raw = "QUERY scanmz(MS2DATA) WHERE MS2PROD=226.18"
# #raw = "QUERY MS2DATA WHERE MS2PROD=226.18 AND MS2PREC=226.1797"
# #raw = "QUERY scannum(MS2DATA) WHERE MS1MZ=XX"
# #raw = "QUERY scannum(MS2DATA) WHERE MS1MZ=XX"
# #raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=226.18 AND MS2PREC=226.1797"
# #raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271 AND MS2PREC=500 AND MS1MZ=100"
# #raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271:MZDELTA=0.01:INTENSITYPERCENT>10 AND MS2PREC=500"
# #raw = "QUERY scanrangesum(MS1DATA, TOLERANCE=0.1) WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2PROD=85.02820:MZDELTA=0.01 AND MS2NL=59.07350:MZDELTA=0.01):MZDELTA=0.01"
# # statements = sqlparse.split(raw)

# # print(statements)

# # first = statements[0]

# # print(sqlparse.format(first, reindent=True, keyword_case='upper'))

# # parsed = sqlparse.parse(raw)[0]
# # for token in parsed.tokens:
# #     print("X", token)

# parsed_output = msql_parser.parse_msql(raw)
# print(parsed_output)


# for line in open("test_queries.txt"):
#     test_query = line.rstrip()
#     msql_parser.parse_msql(test_query)
#     #print(test_query)

# results_df = msql_engine.process_query(raw, "test/GNPS00002_A3_p.mzML")
# print(results_df.head())
# #print(set(results_df["scan"]))