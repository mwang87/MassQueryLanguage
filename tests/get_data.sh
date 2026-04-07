mkdir -p data
cd data

# massiveproxy.gnps2.org enforces per-IP rate limiting (~1 request per 70 seconds).
# Use --retry-on-http-error=429 with exponential backoff (--waitretry=120, --tries=10)
# so wget retries automatically after waiting long enough for the rate limit to reset.
download() {
    wget --no-verbose --tries=10 --waitretry=120 --retry-on-http-error=429 --output-document="$1" "$2"
    sleep 5
}

download GNPS00002_A3_p.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000084494/ccms_peak/raw/GNPS00002_A3_p.mzML"
# mzml (lowercase) is the same file as mzML - copy to avoid an extra rate-limited request
cp GNPS00002_A3_p.mzML GNPS00002_A3_p.mzml
download GNPS00002_A10_n.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000084494/ccms_peak/raw/GNPS00002_A10_n.mzML"
download QC_0.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000085852/ccms_peak/QC_raw/QC_0.mzML"
download bld_plt1_07_120_1.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000085944/ccms_peak/raw_data/bld_plt1_07_120_1.mzML"
download NS_1x_test.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000087352/updates/2021-05-03_allegraaron_95d2215b/peak/NS_1x_test.mzML"
download JB_182_2_fe.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000084289/ccms_peak/JB_182_2_fe.mzML"
download S_N2_neutral_Zn.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000083387/updates/2019-11-12_allegraaron_e893cb7e/peak/S_N2_neutral_Zn.mzML"
download gnps-library.json "https://external.gnps2.org/gnpslibrary/GNPS-LIBRARY.json"
download specs_ms.mgf "https://massive.ucsd.edu/ProteoSAFe/DownloadResultFile?task=5ecfcf81cb3c471698995b194d8246a0&block=main&file=spectra/specs_ms.mgf"
download 1810E-II.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000084691/ccms_peak/1810E-II.mzML"
download T04251505.mzXML "https://massiveproxy.gnps2.org/massiveproxy/MSV000082797/ccms_peak/raw/MTBLS368/T04251505.mzXML"
download isa_9_fe.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000084030/ccms_peak/isa_9_fe.mzML"
download 01308_H02_P013387_B00_N16_R1.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000083508/ccms_peak/colon/Trypsin_HCD_QExactiveplus/01308_H02_P013387_B00_N16_R1.mzML"
download 119A-24.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000083461/ccms_peak/mzXML/119A-24.mzML"
download Hui_N2_fe.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000084628/ccms_peak/Hui_N2_fe.mzML"
download meoh_water_ms2_1_31_1_395.mzML "https://proteomics2.ucsd.edu/ProteoSAFe/DownloadResultFile?task=2eb041215fdd4f89a2ef91be70752e16&file=workflow_results/spectra/meoh_water_ms2_1_31_1_395.mzML&block=main&process_html=false"
download MMSRG_027.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000088268/peak/Anelize%20and%20Hector/MMSRG_027.mzML"
download featurelist_pos.mgf "https://massiveproxy.gnps2.org/massiveproxy/MSV000086995/updates/2022-01-18_mwang87_e619431a/peak/bahbobeh/featurelist_pos.mgf"
download GT15A.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000087048/ccms_peak/Green_Tea_manuscript_data/GT15A.mzML"
download PLT2_B1.mzML "https://massiveproxy.gnps2.org/massiveproxy/MSV000088800/ccms_peak/NRRL_PLT2_czapek_solid_raw/PLT2_B1.mzML"

# --- Diagnostic: print file sizes and first 5 lines of each downloaded file ---
echo ""
echo "=== Downloaded file sizes ==="
ls -lh .

echo ""
echo "=== File heads for debugging ==="
for f in *.mzML *.mzml *.mzXML *.mgf *.json; do
    [ -f "$f" ] || continue
    echo ""
    echo "--- $f ($(wc -c < "$f") bytes) ---"
    head -5 "$f"
done
