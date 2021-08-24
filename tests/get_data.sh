mkdir -p data
cd data
wget --no-verbose --output-document=GNPS00002_A3_p.mzML ftp://massive.ucsd.edu/MSV000084494/ccms_peak/raw/GNPS00002_A3_p.mzML
wget --no-verbose --output-document=QC_0.mzML ftp://massive.ucsd.edu/MSV000085852/ccms_peak/QC_raw/QC_0.mzML
wget --no-verbose --output-document=bld_plt1_07_120_1.mzML ftp://massive.ucsd.edu/MSV000085944/ccms_peak/raw_data/bld_plt1_07_120_1.mzML
wget --no-verbose --output-document=NS_1x_test.mzML ftp://massive.ucsd.edu/MSV000087352/updates/2021-05-03_allegraaron_95d2215b/peak/NS_1x_test.mzML
wget --no-verbose --output-document=JB_182_2_fe.mzML ftp://massive.ucsd.edu/MSV000084289/ccms_peak/JB_182_2_fe.mzML
wget --no-verbose --output-document=S_N2_neutral_Zn.mzML ftp://massive.ucsd.edu/MSV000083387/updates/2019-11-12_allegraaron_e893cb7e/peak/S_N2_neutral_Zn.mzML
wget --no-verbose --output-document=gnps-library.json https://gnps-external.ucsd.edu/gnpslibrary/GNPS-LIBRARY.json
wget --no-verbose --output-document=specs_ms.mgf "http://massive.ucsd.edu/ProteoSAFe/DownloadResultFile?task=5ecfcf81cb3c471698995b194d8246a0&block=main&file=spectra/specs_ms.mgf"
wget --no-verbose --output-document=1810E-II.mzML "https://massive.ucsd.edu/ProteoSAFe/DownloadResultFile?file=f.MSV000084691/ccms_peak/1810E-II.mzML&forceDownload=true"
wget --no-verbose --output-document=KoLRI_24666_Cent.mzML "http://massive.ucsd.edu/ProteoSAFe/DownloadResultFile?task=5fc1673650f446c1b803c6391d15d0e7&block=main&file=kbkang/Lichen_library/KoLRI_24666_Cent.mzML"
wget --no-verbose --output-document=T04251505.mzXML "https://massive.ucsd.edu/ProteoSAFe/DownloadResultFile?file=f.MSV000082797/ccms_peak/raw/MTBLS368/T04251505.mzXML&forceDownload=true"
wget --no-verbose --output-document=isa_9_fe.mzML "https://massive.ucsd.edu/ProteoSAFe/DownloadResultFile?file=f.MSV000084030/ccms_peak/isa_9_fe.mzML&forceDownload=true"
wget --no-verbose --output-document=01308_H02_P013387_B00_N16_R1.mzML "ftp://massive.ucsd.edu/MSV000083508/ccms_peak/colon/Trypsin_HCD_QExactiveplus/01308_H02_P013387_B00_N16_R1.mzML"