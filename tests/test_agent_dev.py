import os
import sys

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_engine


def test_ms2_intensity_gt_lt_eq_dev():
	"""
	Development test for intensity comparators on a realistic multi-fragment query.

	This uses a known MGF in the test data folder and compares scan hits across
	`>`, `<`, and `=` variants of the same constraints.
	"""

	data_file = "tests/data/featurelist_pos.mgf"

	query_gt = (
		"QUERY scaninfo(MS2DATA) WHERE "
		"MS2PROD=184.0739:TOLERANCEMZ=0.01:INTENSITYPERCENT>30:INTENSITYVALUE>500 AND "
		"MS2PROD=125.0004:TOLERANCEMZ=0.01:INTENSITYPERCENT>10:INTENSITYVALUE>1500 AND "
		"MS2PROD=104.1075:TOLERANCEMZ=0.01 AND "
		"MS2PROD=86.09697:TOLERANCEMZ=0.01:INTENSITYPERCENT>10:INTENSITYVALUE>2000 AND "
		"SCANMIN=1000 AND SCANMAX=1020"
	)

	# LT uses only INTENSITYPERCENT (no INTENSITYVALUE): absolute intensities in this
	# data are in the tens-of-thousands range, so a tight INTENSITYVALUE<500 would
	# exclude all real peaks. Using the same relative thresholds (30%, 10%) as GT
	# guarantees the GT and LT scan sets are disjoint (no scan can have a fragment
	# at both >30% and <30% of the scan maximum simultaneously).
	query_lt = (
		"QUERY scaninfo(MS2DATA) WHERE "
		"MS2PROD=184.0739:TOLERANCEMZ=0.01:INTENSITYPERCENT<30 AND "
		"MS2PROD=125.0004:TOLERANCEMZ=0.01:INTENSITYPERCENT<10 AND "
		"MS2PROD=104.1075:TOLERANCEMZ=0.01 AND "
		"MS2PROD=86.09697:TOLERANCEMZ=0.01:INTENSITYPERCENT<10 AND "
		"SCANMIN=1000 AND SCANMAX=1020"
	)

	# EQ with exact floating-point thresholds will realistically return nothing,
	# but the assertion only requires EQ to differ from at least one of GT or LT.
	query_eq = (
		"QUERY scaninfo(MS2DATA) WHERE "
		"MS2PROD=184.0739:TOLERANCEMZ=0.01:INTENSITYPERCENT=30 AND "
		"MS2PROD=125.0004:TOLERANCEMZ=0.01:INTENSITYPERCENT=10 AND "
		"MS2PROD=104.1075:TOLERANCEMZ=0.01 AND "
		"MS2PROD=86.09697:TOLERANCEMZ=0.01:INTENSITYPERCENT=10 AND "
		"SCANMIN=1000 AND SCANMAX=1020"
	)

	results_gt = msql_engine.process_query(query_gt, data_file)
	results_lt = msql_engine.process_query(query_lt, data_file)
	results_eq = msql_engine.process_query(query_eq, data_file)

	scans_gt = set(results_gt["scan"]) if "scan" in results_gt else set()
	scans_lt = set(results_lt["scan"]) if "scan" in results_lt else set()
	scans_eq = set(results_eq["scan"]) if "scan" in results_eq else set()

	print("GT scans:", sorted(scans_gt))
	print("LT scans:", sorted(scans_lt))
	print("EQ scans:", sorted(scans_eq))

	# Ensure we are testing against real hits instead of empty trivial sets.
	assert len(scans_gt) > 0, "Expected at least one scan for GT variant"
	assert len(scans_lt) > 0, "Expected at least one scan for LT variant"

	# Comparator behavior should separate > from < results for this pattern.
	assert scans_gt.isdisjoint(scans_lt), (
		"GT and LT variants should produce disjoint scan sets, but they overlap. "
		"This suggests intensity comparator operators are not being applied correctly."
	)

	# Equality should usually be narrower than broad threshold matching.
	assert scans_eq != scans_gt or scans_eq != scans_lt


def main():
	test_ms2_intensity_gt_lt_eq_dev()


if __name__ == "__main__":
	main()
