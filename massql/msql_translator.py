from massql import msql_parser

def translate_query(query, language="english"):
    parsed_query = msql_parser.parse_msql(query)

    sentences = []
    sentences.append(_translate_querytype(parsed_query["querytype"], language=language))

    if len(parsed_query["conditions"]) > 0:
        if language == "english":
            sentences.append("The following conditions are applied to find scans in the mass spec data.")
        if language == "russian":
            sentences.append("Применяются следующие условия для поиска экземпляров в массиве данных.")
        elif language == "korean":
            sentences.append("매스 스펙트럼으로 부터의 스캔 검색조건은 아래와 같습니다.")
        elif language == "chinese":
            sentences.append("这些条件被用于在数据中找到扫描数据。")
        elif language == "french":
            sentences.append("Les conditions suivantes sont appliquées pour trouver les échantillons dans les données du spectrométrie.")
        elif language == "german":
            sentences.append("Die folgenden Bedingungen werden auf massenspektrometrische Daten angewendet um Spektren zu finden.")
        elif language == "spanish":
            sentences.append("Las siguientes condiciones son aplicadas para encontrar los espectros de masas en los datos de espectrometria.")
        elif language == "portuguese":
            sentences.append("As condições a seguir sāo aplicadas para buscar scans nos dados de espectrometria de massas.")
        

    for condition in parsed_query["conditions"]:
        sentences.append(_translate_condition(condition, language=language))

    return "\n".join(sentences)


def _translate_querytype(querytype, language="english"):
    # return information
    ms_level = "MS1"
    if querytype["datatype"] == "datams1data":
        ms_level = "MS1"
    if querytype["datatype"] == "datams2data":
        ms_level = "MS2"

    if querytype["function"] == "functionscaninfo":
        if language == "english":
            return "Returning the scan information on {}.".format(ms_level)
        if language == "russian":
            return "Возвращает информацию о скане на {}.".format(ms_level)
        elif language == "korean":
            return "{} 데이터상의 스캔 정보를 반환합니다.".format(ms_level)
        elif language == "chinese":
            return "返回{}的扫描信息".format(ms_level)
        elif language == "french":
            return "Retourne les informations sur le scan {}.".format(ms_level)
        elif language == "german":
            return "Zurückgeben der Scaninformation von {}.".format(ms_level)
        elif language == "spanish":
            return "Generando información de {}.".format(ms_level)
        elif language == "portuguese":
            return "Encontrando scans com informações de {}.".format(ms_level)
        
    if querytype["function"] == "functionscansum":
        if language == "english":
            return "Returning the summed scan information on {}.".format(ms_level)
        if language == "russian":
            return "Возвращает информацию о суммированном скане на {}.".format(ms_level)
        elif language == "korean":
            return "스칼라를 {} 데이터로 더하기.".format(ms_level)
        elif language == "chinese":
            return "返回{}的总计扫描信息".format(ms_level)
        elif language == "french":
            return "Retourne les informations sur le scan somme de {}.".format(ms_level)
        elif language == "german":
            return "Zurückgeben der zusammengefassten Scaninformation von {}.".format(ms_level)
        elif language == "spanish":
            return "Retornando información de cada espectro de {}.".format(ms_level)
        elif language == "portuguese":
            return "Retornando informação de cada espectro de {}.".format(ms_level)
        


    return "Translator {} not implemented, contact Ming".format(querytype["function"])

def _translate_condition(condition, language="english"):
    if "qualifiers" in condition:
        qualifier_string = " " + _translate_qualifiers(condition["qualifiers"], language=language)
    else:
        qualifier_string = ""

    if condition["type"] == "ms2productcondition":
        if language == "english":
            return "Finding MS2 peak at m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers
        if language == "russian":
            return "Поиск MS2 пика по m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "korean":
            return "MS2 질량대 전하비 (m/z): {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "chinese":
            return "寻找m/z{}的MS2峰{}".format(condition["value"][0], qualifier_string)
        elif language == "french":
            return "Trouver un pic MS2 à m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "german":
            return "Hat MS2 Signal bei m/z {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "spanish":
            return "Encontrando pico de MS2 a m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "portuguese":
            return "Buscando ions de MS2 de m/z {} {}.".format(condition["value"][0], qualifier_string)

    if condition["type"] == "ms2neutrallosscondition":
        if language == "english":
            return "Finding MS2 neutral loss peak at m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers
        if language == "russian":
            return "Поиск MS2 нейтраллизации пика по m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "korean":
            return "MS2 전자 소모량 {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "chinese":
            return "在{}的MS2中探测到m/z{}".format(condition["value"][0], qualifier_string)
        elif language == "french":
            return "Trouver un pic MS2 neutral loss à m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "german":
            return "Hat MS2 Neutralverlust von m/z {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "spanish":
            return "Encontrando pico de MS2 de neutral loss en m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "portuguese":
            return "Encontrando peak de neutralização MS2 na m/z {}{}.".format(condition["value"][0], qualifier_string)
    
    if condition["type"] == "ms1mzcondition":
        if language == "english":
            return "Finding MS1 peak at m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers]
        if language == "russian":
            return "Поиск MS1 пика по m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "korean":
            return "MS1 파워 밀도 {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "chinese":
            return "在{}的MS1中找到m/z{}".format(condition["value"][0], qualifier_string)
        elif language == "french":
            return "Trouver un pic MS1 à m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "german":
            return "Hat MS1 Signal bei m/z {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "spanish":
            return "Encontrando pico de MS1 en m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "portuguese":
            return "Buscando ions de MS1 de m/z {}{}.".format(condition["value"][0], qualifier_string)
    
    if condition["type"] == "ms2precursorcondition":
        if language == "english":
            return "Finding MS2 spectra with a precursor m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers
        if language == "russian":
            return "Поиск MS2 по предварительному m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "korean":
            return "MS2 파워 밀도 {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "chinese":
            return "在{}的MS2中找到m/z{}".format(condition["value"][0], qualifier_string)
        elif language == "french":
            return "Trouver des spectres MS2 avec une m/z de précursor {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "german":
            return "Hat MS2 Vorläuferion bei m/z {} {}.".format(condition["value"][0], qualifier_string)
        elif language == "spanish":
            return "Encontrando espectros de MS2 con un precursor m/z {}{}.".format(condition["value"][0], qualifier_string)
        elif language == "portuguese":
            return "Buscando espectros MS2 com m/z de referencia {}{}.".format(condition["value"][0], qualifier_string)

    return "Translator {} not implemented, contact Ming".format(condition["type"])

def _translate_qualifiers(qualifiers, language="english"):
    qualifier_phrases = []

    for qualifier in qualifiers:
        # These are keys, so looking them  up
        if "qualifier" in qualifier:
            qualifier_phrases.append(_translate_qualifier(qualifiers[qualifier], language=language))
    
    if language == "english":
        return "and ".join(qualifier_phrases)
    if language == "russian":
        return "и в".join(qualifier_phrases)
    elif language == "korean":
        return "와 ".join(qualifier_phrases)
    elif language == "chinese":
        return "和 ".join(qualifier_phrases)
    elif language == "french":
        return "et ".join(qualifier_phrases)
    elif language == "german":
        return "und ".join(qualifier_phrases)
    elif language == "spanish":
        return "y ".join(qualifier_phrases)
    elif language == "portuguese":
        return "e ".join(qualifier_phrases)

    return " and ".join(qualifier_phrases)

def _translate_qualifier(qualifier, language="english"):
    if qualifier["name"] == "qualifierppmtolerance":
        if language == "english":
            return "a {} PPM tolerance".format(qualifier["value"])
        if language == "russian":
            return "с {} PPM точность".format(qualifier["value"])
        elif language == "korean":
            return "오차범위 (tolerance): {} ppm 의 조건으로 검색합니다".format(qualifier["value"])
        elif language == "chinese":
            return "允许{} ppm质量偏差".format(qualifier["value"])
        elif language == "french":
            return "une tolérance {} PPM".format(qualifier["value"])
        elif language == "german":
            return "eine {} PPM Abweichung".format(qualifier["value"])
        elif language == "spanish":
            return "con tolerancia de {} PPM".format(qualifier["value"])
        elif language == "portuguese":
            return "com {} ppm de tolerância".format(qualifier["value"])

    if qualifier["name"] == "qualifiermztolerance":
        if language == "english":
            return "a {} m/z tolerance".format(qualifier["value"])
        if language == "russian":
            return "с {} m/z точность".format(qualifier["value"])
        elif language == "korean":
            return "m/z 오차 {} 밀도".format(qualifier["value"])
        elif language == "chinese":
            return "一个{} m/z 容差".format(qualifier["value"])
        elif language == "french":
            return "une tolérance {} m/z".format(qualifier["value"])
        elif language == "german":
            return "eine {} m/z Abweichung".format(qualifier["value"])
        elif language == "spanish":
            return "un {} m/z de tolerancia".format(qualifier["value"])
        elif language == "portuguese":
            return "uma tolerância de {} m/z".format(qualifier["value"])

    if qualifier["name"] == "qualifierintensitypercent":
        if language == "english":
            return "a minimum percent intensity relative to base peak of {}%".format(qualifier["value"])
        if language == "russian":
            return "с минимальной процентной интенсивностью {}%".format(qualifier["value"])
        elif language == "korean":
            return "최소 정상 높이 {}%".format(qualifier["value"])
        elif language == "chinese":
            return "一个最低比值{}%的精确度".format(qualifier["value"])
        elif language == "french":
            return "une intensité minimale relative à la base de {}%".format(qualifier["value"])
        elif language == "german":
            return "eine minimale Intensität relative zum Basispeak von {}%".format(qualifier["value"])
        elif language == "spanish":
            return "un mínimo de {}% de intensidad relativa a base pico".format(qualifier["value"])
        elif language == "portuguese":
            return "uma intensidade mínima relativa ao pico base de {}%".format(qualifier["value"])

    if qualifier["name"] == "qualifierintensityreference":
        if language == "english":
            return "this peak is used as the intensity reference for other peaks in the spectrum"
        if language == "russian":
            return "этот пик используется в качестве интенсивности спектра"
        elif language == "korean":
            return "이 데이터를 이용해 시퀀스에 다른 데이터를 인식한다"
        elif language == "chinese":
            return "这个峰用作输入精确度的参考峰"
        elif language == "french":
            return "ce pico est utilisé comme référence d'intensité pour les autres pics de l'échantillon"
        elif language == "german":
            return "dieses Signal wird als Intensitätsreferenz für andere Signale verwendet"
        elif language == "spanish":
            return "este pico é utilizado como referencia de intensidade para outros picos no espectro"
        elif language == "portuguese":
            return "este pico é usado como referencia de intensidade para outros picos no espectro"

    if qualifier["name"] == "qualifierintensitymatch":
        if language == "english":
            return "an expected relative intensity to reference peak of {}".format(qualifier["value"]) #TODO: we should likely remove the Y or assume it 1.0
        if language == "russian":
            return "соответствующая интенсивность {}".format(qualifier["value"])
        elif language == "korean":
            return "예상 비율 이용시 이용할 대상 데이터의 정보 {}".format(qualifier["value"])
        elif language == "chinese":
            return "一个预期相对于参考峰的精确度 {}".format(qualifier["value"])
        elif language == "french":
            return "une intensité prévu relative à la référence de {}".format(qualifier["value"])
        elif language == "german":
            return "eine erwartete Intensität relativ zum Referenzsignal von {}".format(qualifier["value"])
        elif language == "spanish":
            return "una intensidad esperada relativa ao pico de referencia de {}".format(qualifier["value"])
        elif language == "portuguese":
            return "em uma intensidade relativa esperada ao pico de referencia de {}".format(qualifier["value"])

    if qualifier["name"] == "qualifierintensitytolpercent":
        if language == "english":
            return "accepting variability of {}% in relative intensity".format(qualifier["value"])
        if language == "russian":
            return "принимая на случай {}% в относительной интенсивности".format(qualifier["value"])
        elif language == "korean":
            return "이상한 {}%의 비율의 신체 이용 허용".format(qualifier["value"])
        elif language == "chinese":
            return "接受{}%的精确度变动".format(qualifier["value"])
        elif language == "french":
            return "accepter la variabilité de {}% en intensité relative".format(qualifier["value"])
        elif language == "german":
            return "eine Toleranz von {}% in der erwarteten relativen Intensität".format(qualifier["value"])
        elif language == "spanish":
            return "aceptando variabilidad de {}% de intensidad relativa".format(qualifier["value"])
        elif language == "portuguese":
            return "e aceitando uma variabilidade de {}% da intensidade relativa".format(qualifier["value"])

    return "Translator {} not implemented, contact Ming".format(qualifier["name"])
