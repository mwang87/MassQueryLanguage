from lib2to3.pytree import convert
import requests

def convert_motifdb_to_massql(usi_motifdb):
    url = "https://metabolomics-usi.ucsd.edu/json/"
    r = requests.get(url, params={'usi1': usi_motifdb})

    peaks = r.json()['peaks']

    print(peaks)

    query = "QUERY scaninfo(MS2DATA) WHERE "

    conditions = " AND ".join(["MS2PROD={}".format(peak[0]) for peak in peaks])
    query += conditions

    return query


def main():
    convert_motifdb_to_massql("mzspec:MOTIFDB::accession:151065")

if __name__ == "__main__":
    main()