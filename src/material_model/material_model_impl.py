"""AaC Plugin implementation module for the Material-Model plugin."""
# NOTE: It is safe to edit this file.
# This file is only initially generated by the aac gen-plugin, and it won't be overwritten if the file already exists.

import csv
import math
from os import path, makedirs
from typing import List

from aac.plugins.plugin_execution import PluginExecutionResult, plugin_result
from aac.validate import validated_source
from aac.lang.definitions.definition import Definition

PLUGIN_NAME = "Material-Model"


SITES = {}
ASSEMBLIES = {}
PARTS = {}

NAME_SEPARATOR = " / "


def gen_bom(architecture_file: str, output_directory: str) -> PluginExecutionResult:
    """
    Generates a CSV Bill of Materials (BOM) from a list of site models.

    Args:
        architecture_file (str): The site model to convert into a BOM.
        output_directory (str): The directory where the BOM file should be placed.
    """

    def generate_bom():
        definitions = _get_parsed_models(architecture_file)

        root_sites = _get_root_sites_and_setup_data(definitions)

        line_items = []
        for site_name in root_sites.keys():
            line_items.extend(_process_site([], [], "", [], root_sites[site_name]))

        # just in case, let's make sure the output directory exists
        if not path.lexists(output_directory):
            makedirs(output_directory)

        file_name = "bom.csv"
        output_path = path.join(output_directory, file_name)
        with open(output_path, "w") as output:
            writer = csv.DictWriter(output, fieldnames=_get_header())
            writer.writeheader()
            writer.writerows(line_items)

        return f"{len(line_items)} BOM line items written to {output_path}"

    with plugin_result(PLUGIN_NAME, generate_bom) as result:
        return result


def _get_parsed_models(architecture_file: str) -> List[Definition]:
    with validated_source(architecture_file) as result:
        return result.definitions


def _get_root_sites_and_setup_data(definitions):
    root_sites = {}
    site_tree = {}

    for definition in definitions:
        if definition.get_root_key() in ["site"]:
            # save site by name for easy access
            SITES[definition.name] = definition
            root_sites[definition.name] = definition
            # save site tree data
            if "sub-sites" in definition.structure["site"].keys():
                subs = []
                for sub in definition.structure["site"]["sub-sites"]:
                    subs.append(sub["site-ref"])
                site_tree[definition.name] = subs

            else:
                site_tree[definition.name] = []
        if definition.get_root_key() in ["assembly"]:
            # save assembly by name for easy access
            ASSEMBLIES[definition.name] = definition
        if definition.get_root_key() in ["part"]:
            # save part by name for easy access
            PARTS[definition.name] = definition

    # remove child sites from root_sites
    for key in site_tree:
        for sub in site_tree[key]:
            if sub:
                root_sites.pop(sub)

    return root_sites


def _process_site(parent_name_list, quantity_factors, parent_need_date, parent_location, site):
    ret_val = []

    name_list = parent_name_list.copy()
    name_list.append(site.name)

    need_date = parent_need_date  # intentionally override parent need dates with child need dates
    if "need_date" in site.structure["site"].keys():
        need_date = site.structure["site"]["need_date"]

    location = parent_location.copy()
    if "location" in site.structure["site"].keys():
        location.append(site.structure["site"]["location"])

    if "parts" in site.structure["site"].keys():
        for part_ref in site.structure["site"]["parts"]:
            part_name = part_ref["part-ref"]
            part_quantity_factors = quantity_factors.copy()
            part_quantity_factors.append(part_ref["quantity"])
            ret_val.append(_generate_bom_line(name_list, part_quantity_factors, need_date, location, PARTS[part_name]))

    if "sub-sites" in site.structure["site"].keys():
        for site_ref in site.structure["site"]["sub-sites"]:
            sub_name = site_ref["site-ref"]
            sub_quantity_factors = quantity_factors.copy()
            sub_quantity_factors.append(site_ref["quantity"])
            ret_val.extend(_process_site(name_list, sub_quantity_factors, need_date, location, SITES[sub_name]))

    if "assemblies" in site.structure["site"].keys():
        for assembly_ref in site.structure["site"]["assemblies"]:
            sub_name = assembly_ref["assembly-ref"]
            sub_quantity_factors = quantity_factors.copy()
            sub_quantity_factors.append(assembly_ref["quantity"])
            ret_val.extend(_process_assembly(name_list, sub_quantity_factors, need_date, location, ASSEMBLIES[sub_name]))

    return ret_val


def _process_assembly(parent_name_list, quantity_factors, parent_need_date, parent_location, assembly):
    ret_val = []

    name_list = parent_name_list.copy()
    name_list.append(assembly.name)

    if "parts" in assembly.structure["assembly"].keys():
        for part_ref in assembly.structure["assembly"]["parts"]:
            part_name = part_ref["part-ref"]
            part_quantity_factors = quantity_factors.copy()
            part_quantity_factors.append(part_ref["quantity"])
            ret_val.append(
                _generate_bom_line(name_list, part_quantity_factors, parent_need_date, parent_location, PARTS[part_name])
            )

    if "sub-assemblies" in assembly.structure["assembly"].keys():
        for sub_ref in assembly.structure["assembly"]["sub-assemblies"]:
            sub_name = sub_ref["assembly-ref"]
            sub_quantity_factors = quantity_factors.copy()
            sub_quantity_factors.append(sub_ref["quantity"])
            ret_val.extend(
                _process_assembly(name_list, sub_quantity_factors, parent_need_date, parent_location, ASSEMBLIES[sub_name])
            )

    return ret_val


def _get_header():
    return ["name", "make", "model", "description", "quantity", "unit_cost", "total_cost", "need_date", "location"]


def _generate_bom_line(parent_name_list, quantity_factors, need_date, location_list, part):

    ret_val = {}

    # populate the name field
    name = ""
    for item in parent_name_list:
        name += item + NAME_SEPARATOR
    ret_val["name"] = name + part.name

    # populate the need_date field
    ret_val["need_date"] = need_date

    # populate the location field
    location = ""
    first = True
    for item in location_list:
        if first:
            first = False
            location = item
        else:
            location += NAME_SEPARATOR + item
    ret_val["location"] = location

    # populate the quantity field
    ret_val["quantity"] = math.prod(quantity_factors)

    # populate the fields directly taken from the part
    ret_val["make"] = part.structure["part"]["make"]
    ret_val["model"] = part.structure["part"]["model"]
    ret_val["description"] = part.structure["part"]["description"]
    ret_val["unit_cost"] = part.structure["part"]["unit_cost"]

    # populate total cost field
    ret_val["total_cost"] = ret_val["quantity"] * ret_val["unit_cost"]

    return ret_val
