import msql_parser
import msql_engine
import json
import pytest

def test_noquery():
    query = "QUERY scaninfo(MS2DATA)"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_simple_ms2():
    query = "QUERY MS2DATA WHERE MS2PROD=226.18"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")

def test_simple_ms2_qualifier():
    query = "QUERY MS2DATA WHERE MS2PROD=226.18:TOLERANCEPPM=5"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_simple_ms2_twoqualifier():
    query = "QUERY MS2DATA WHERE MS2PROD=226.18:TOLERANCEPPM=5:INTENSITYVALUE=1"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_simple_ms2_twoconditions():
    query = "QUERY MS2DATA WHERE MS2PROD=226.18:TOLERANCEPPM=5:INTENSITYVALUE=1 AND MS2PROD=226.20:TOLERANCEPPM=5:INTENSITYVALUE=1"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_xic():
    query = "QUERY scansum(MS1DATA) WHERE MS1MZ=100:TOLERANCEMZ=0.1"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_simple_info_ms2():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_simple_ms1():
    query = "QUERY MS1DATA WHERE MS2PROD=226.18"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_qc_ms1_ms2peak():
    query = "QUERY MS1DATA WHERE MS2PROD=156.01"
    results_df = msql_engine.process_query(query, "test/QC_0.mzML")
    print(set(results_df["scan"]))
    assert(len(results_df) > 1000)

def test_diphen():
    query = "QUERY scannum(MS2DATA) WHERE MS2PROD=167.0857:TOLERANCEPPM=5"
    print(msql_parser.parse_msql(query))
    results_df = msql_engine.process_query(query, "test/bld_plt1_07_120_1.mzML")
    assert(1235 in list(results_df["scan"]))
    assert(1316 in list(results_df["scan"]))
    assert(1293 in list(results_df["scan"]))

    print(results_df)

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

def test_variable_parse():
    # This finds the sum of the MS1 of the MS2 spectrum with 
    query = "QUERY scaninfo(MS2DATA) WHERE MS1MZ=X AND MS2PREC=X AND MS2PROD=119.09"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))

def test_variable():
    # This finds the sum of the MS1 of the MS2 spectrum with 
    #query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=119.09"
    query = "QUERY scaninfo(MS2DATA) WHERE MS1MZ=X AND MS2PREC=X AND MS2PROD=119.09"
    #query = "QUERY scaninfo(MS2DATA) WHERE MS1MZ=X"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))

    assert(len(parse_obj["conditions"]) == 3)

    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

@pytest.mark.skip(reason="too slow")
def test_variable_ms1():
    # This is looking for ms1 scans with a +18 delta, should include scan 52
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=X AND MS1MZ=X+18.031"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))

    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_subquery():
    #query = "QUERY scanrangesum(MS1DATA, TOLERANCE=0.1) WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2NL=176.0321 AND MS2PROD=85.02915)"
    query = "QUERY MS1DATA WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2NL=176.0321 AND MS2PROD=85.02915)"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(json.dumps(msql_parser.parse_msql(query), indent=4))
    print(results_df)

def test_filter():
    query = "QUERY scansum(MS1DATA) FILTER MS1MZ=100"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_filterms2():
    query = "QUERY MS2DATA FILTER MS2PROD=226.18"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_min_intensity():
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=226.18:INTENSITYVALUE=300000"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)
    
    assert(len(results_df) == 6)
    

def test_min_intensitypercent():
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=226.18:INTENSITYPERCENT=1"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

    assert(len(results_df) == 8)

def test_where_and_filter():
    query = "QUERY MS2DATA WHERE MS2PROD=70.06:TOLERANCEMZ=0.01:INTENSITYVALUE>10000 FILTER MS2PROD=70.06:TOLERANCEMZ=0.1"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))

def test_ms1_iron():
    #msql_engine.init_ray()

    # query = "QUERY scaninfo(MS1DATA) WHERE \
    #         RTMIN=3.06 \
    #         AND RTMAX=3.07"
    query = "QUERY scaninfo(MS1DATA) \
            WHERE \
            RTMIN=3.03 \
            AND RTMAX=3.05 \
            AND MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 \
            AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE \
            FILTER \
            MS1MZ=X"
    parse_obj = msql_parser.parse_msql(query)
    print(parse_obj)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/JB_182_2_fe.mzML")
    print(results_df)
    assert(1223 in list(results_df["scan"]))


def test_ms1_iron_X_changes_intensity():
    query = "QUERY scaninfo(MS2DATA) WHERE \
        MS1MZ=X-2:INTENSITYMATCH=Y*(0.0608+(.000002*X)):INTENSITYMATCHPERCENT=25 AND \
        MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE:INTENSITYPERCENT=5 AND \
        MS2PREC=X"
    parse_obj = msql_parser.parse_msql(query)
    print(parse_obj)

def test_ms1_iron_min_intensity():
    #msql_engine.init_ray()

    query = "QUERY scaninfo(MS1DATA) \
            WHERE \
            RTMIN=3.03 \
            AND RTMAX=3.05 \
            AND MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 \
            AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE:INTENSITYPERCENT=10 \
            FILTER \
            MS1MZ=X"
    parse_obj = msql_parser.parse_msql(query)
    print(parse_obj)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/JB_182_2_fe.mzML")
    print(results_df)
    assert(1223 in list(results_df["scan"]))
    assert(len(results_df) == 10)

def test_ms1_iron_min_intensity_m2_prec():
    #msql_engine.init_ray()

    query = "QUERY scaninfo(MS2DATA) \
            WHERE \
            RTMIN=2.8 \
            AND RTMAX=3.05 \
            AND MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=30 \
            AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE:INTENSITYPERCENT=5 \
            AND MS2PREC=X \
            FILTER \
            MS1MZ=X"
    parse_obj = msql_parser.parse_msql(query)
    print(parse_obj)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/JB_182_2_fe.mzML")
    print(results_df)
    assert(1214 in list(results_df["scan"]))

def test_ms1_cu():
    msql_engine.init_ray()

    query = "QUERY scaninfo(MS1DATA) \
            WHERE \
            RTMIN=4.23 \
            AND RTMAX=4.28 \
            AND MS1MZ=X-2:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE \
            AND MS1MZ=X:INTENSITYMATCH=Y*0.574:INTENSITYMATCHPERCENT=25 \
            AND MS1MZ=X+2:INTENSITYMATCH=Y*0.387:INTENSITYMATCHPERCENT=25 \
            FILTER \
            MS1MZ=X"
    parse_obj = msql_parser.parse_msql(query)
    print(parse_obj)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/S_N2_neutral_Zn.mzML")
    print(results_df)

def test_ms1_filter():
    query = "QUERY scansum(MS1DATA) WHERE MS1MZ=601.3580:TOLERANCEMZ=0.1:INTENSITYPERCENT>0.05 AND MS1MZ=654.2665:TOLERANCEMZ=0.1:INTENSITYPERCENT>0.05 FILTER MS1MZ=601.3580"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/JB_182_2_fe.mzML")
    print(results_df)

def test_ms1_filtered_by_ms2():
    query = "QUERY scansum(MS1DATA) WHERE MS2PROD=309.2:TOLERANCEMZ=0.1"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_intensity_int_parse():
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=425.2898:TOLERANCEMZ=0.1:INTENSITYPERCENT>1 AND MS2PROD=353.25:TOLERANCEMZ=0.1:INTENSITYPERCENT>80 AND MS1MZ=478.1991:TOLERANCEMZ=0.1:INTENSITYPERCENT>1"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))

def test_intensity_match():
    query = "QUERY scaninfo(MS1DATA) WHERE \
        MS1MZ=147.09:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE AND \
        MS1MZ=148.0945:INTENSITYMATCH=Y*0.1:INTENSITYMATCHPERCENT=1"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_rt_filter():
    query = "QUERY scaninfo(MS1DATA) WHERE \
        RTMIN=0.1 AND RTMAX=0.3"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

def test_neutral_loss_intensity():
    query = "QUERY scaninfo(MS2DATA) WHERE \
            MS2NL=183.096:TOLERANCEMZ=0.1:INTENSITYPERCENT=50"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/XA_Frac_6.mzML")
    print(results_df)

def test_gnps_library():
    query = "QUERY scaninfo(MS2DATA) WHERE \
            MS2PROD=271.06:TOLERANCEMZ=0.1:INTENSITYPERCENT=50"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/gnps-library.json")
    print(results_df)

def test_gnps_full_library():
    query = "QUERY scaninfo(MS2DATA) WHERE \
            MS2PROD=271.06:TOLERANCEMZ=0.1:INTENSITYPERCENT=50"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/gnps.json")
    print(results_df)


def test_networking_mgf_library():
    query = "QUERY scaninfo(MS2DATA) WHERE \
            MS2PROD=86.10:TOLERANCEMZ=0.1:INTENSITYPERCENT=50"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/specs_ms.mgf")
    print(results_df)
    assert("2" in list(results_df["scan"]))
    

@pytest.mark.skip(reason="too slow")
def test_double_brominated():
    #msql_engine.init_ray()

    query = "QUERY scaninfo(MS1DATA) WHERE \
        RTMIN=11.6 \
        AND RTMAX=12.2 \
        AND MS1MZ=X:TOLERANCEMZ=0.1:INTENSITYPERCENT=25:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE \
        AND MS1MZ=X+2:TOLERANCEMZ=0.1:INTENSITYMATCH=Y*0.5:INTENSITYMATCHPERCENT=30 \
        AND MS1MZ=X-2:TOLERANCEMZ=0.1:INTENSITYMATCH=Y*0.5:INTENSITYMATCHPERCENT=30 \
        AND MS1MZ=X+4:TOLERANCEMZ=0.3:INTENSITYMATCH=Y*0.25:INTENSITYMATCHPERCENT=30 \
        AND MS1MZ=X-4:TOLERANCEMZ=0.3:INTENSITYMATCH=Y*0.25:INTENSITYMATCHPERCENT=30"

    # query = "QUERY scaninfo(MS1DATA) WHERE \
    #     RTMIN=11.6 \
    #     AND RTMAX=12.2 \
    #     AND MS1MZ=614.79895019:TOLERANCEMZ=0.1:INTENSITYPERCENT=25:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE \
    #     AND MS1MZ=616.79895019:TOLERANCEMZ=0.1:INTENSITYMATCH=Y*0.5:INTENSITYMATCHPERCENT=30 \
    #     AND MS1MZ=612.79895019:TOLERANCEMZ=0.1:INTENSITYMATCH=Y*0.5:INTENSITYMATCHPERCENT=30 \
    #     AND MS1MZ=618.79895019:TOLERANCEMZ=0.3:INTENSITYMATCH=Y*0.25:INTENSITYMATCHPERCENT=30 \
    #     AND MS1MZ=610.79895019:TOLERANCEMZ=0.3:INTENSITYMATCH=Y*0.25:INTENSITYMATCHPERCENT=30"

    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/1810E-II.mzML")
    print(results_df)
    assert(474 in list(results_df["scan"]))


# @pytest.mark.skip(reason="too slow")
# def test_albicidin_tag():
#     query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X:TOLERANCEMZ=0.1:INTENSITYPERCENT=5 \
#         AND MS2PROD=X+119.1 :TOLERANCEMZ=0.1:INTENSITYPERCENT=5 \
#         AND MS2PROD=X+284.0 :TOLERANCEMZ=0.1:INTENSITYPERCENT=5"
#     parse_obj = msql_parser.parse_msql(query)
#     print(json.dumps(parse_obj, indent=4))
#     results_df = msql_engine.process_query(query, "test/XA_Frac_6.mzML")
#     print(results_df)

@pytest.mark.skip(reason="too slow")
def test_swath():
    query = "QUERY scansum(MS2DATA) WHERE MS2PREC=714.55 FILTER \
        MS2PROD=714.34"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))
    results_df = msql_engine.process_query(query, "test/170425_01_Edith_120417_CCF_01.mzML")
    print(results_df)

def test_agilent():
    query = "QUERY scaninfo(MS2DATA)"
    results_df = msql_engine.process_query(query, "test/20190310_MSMSpos_marine_water_20180510_CBTheaFoss_1.mzML")
    

def test_parse():        
    for line in open("test_queries.txt"):
        test_query = line.rstrip()
        print(test_query)
        msql_parser.parse_msql(test_query)

def test_query():
    for line in open("test_queries.txt"):
        test_query = line.rstrip()
        print(test_query)
        msql_engine.process_query(test_query, "test/bld_plt1_07_120_1.mzML")

def test_load():
    ms1_df, ms2_df = msql_engine._load_data("test/JB_182_2_fe.mzML", cache=False)

def main():
    #msql_engine.init_ray()
    
    #test_noquery()
    #test_simple_ms2_twoqualifier()
    #test_simple_ms2_twoconditions()
    #test_diphen()
    #test_diphen_nl()
    #test_diphen_combo()
    #test_simple_info_ms2()
    #test_parse()
    #test_query()
    #test_xic()
    #test_subquery()
    #test_variable_parse()
    #test_variable()
    #test_variable_ms1()
    #test_filter()
    #test_filterms2()
    #test_where_and_filter()
    #test_min_intensity()
    #test_min_intensitypercent()
    #test_ms1_iron()
    #test_ms1_filter()
    #test_intensity_int_parse()
    #test_parse()
    #test_intensity_match()
    #test_rt_filter()
    #test_load()
    #test_ms1_iron()
    #test_ms1_iron_min_intensity()
    #test_ms1_iron_min_intensity_m2_prec()
    #test_ms1_filtered_by_ms2()
    #test_ms1_cu()
    #test_neutral_loss_intensity()
    #test_gnps_library()
    #test_gnps_full_library()
    #test_networking_mgf_library()
    #test_swath()
    #test_albicidin_tag()
    #test_double_brominated()
    #test_agilent()
    test_ms1_iron_X_changes_intensity()

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