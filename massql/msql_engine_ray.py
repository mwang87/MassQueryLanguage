from massql.msql_engine import _executeconditions_query, _executecollate_query
import ray

@ray.remote
def _executeconditions_query_ray(parsed_dict_list, input_filename, ms1_input_df=None, ms2_input_df=None, cache=True):
    """
    Here we will use parallel ray, we will give a list of dictionaries to query, and return a list of results that are collated

    Args:
        parsed_dict_list ([type]): [description]
        input_filename ([type]): [description]
        ms1_input_df ([type], optional): [description]. Defaults to None.
        ms2_input_df ([type], optional): [description]. Defaults to None.
        cache (bool, optional): [description]. Defaults to True.

    Returns:
        [type]: [description]
    """

    collated_list = []

    for parsed_dict in parsed_dict_list:
        ms1_df, ms2_df = _executeconditions_query(parsed_dict, input_filename, ms1_input_df=ms1_input_df, ms2_input_df=ms2_input_df, cache=cache)

        collated_df = _executecollate_query(parsed_dict, ms1_df, ms2_df)
        collated_list.append(collated_df)

    return collated_list