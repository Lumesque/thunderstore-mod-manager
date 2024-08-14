from dataclasses import dataclass, field
from collections import Counter, defaultdict
from pathlib import Path
from ..t_api import ThunderstoreAPI
import warnings
import requests
import zipfile
import click
import io
import os
import tempfile
import shutil
from typing import List, Dict, ClassVar, Optional
from functools import reduce

@dataclass
class ModDownloader:
    api: ThunderstoreAPI
    try_deprecated: bool = True
    use_latest_date: bool = True

    def download(self, list_of_versions, output_directory):
        #path = Path(t, "BepInEx", "plugins")
        #path.mkdir(exist_ok=True, parents=True)
        with click.progressbar(list_of_versions, item_show_func = lambda x: x.name if x is not None else "", label='Downloading mod') as _list:
            for version in _list:
                download_url = version.download_url
                r = requests.get(download_url, stream=True)
                if not r.ok:
                    raise ValueError(f"Could not download from {download_url}")
                z = zipfile.ZipFile(io.BytesIO(r.content))
                z.extractall(output_directory)

    def get_download_list_by_name(self, list_of_mods):
        mod_names = [self._get_mod_by_name(mod_name) for mod_name in list_of_mods]
        mod_names = self.handle_dependencies(mod_names)
        out = [
            self.api.get_package_by_fullname(f"{owner}-{name}", owner=owner, version=version)
            for owner, name, version in [x.split('-') for x in set(mod_names)]
        ]
        return reduce(lambda x,y: x+y, out)

    def _get_mod_by_name(self, mod_name):
        # There is no support for spaces, so use this instead
        mod_name = mod_name.replace(' ', '_')
        api = self.api
        out = api.get_packages_by_name(mod_name)
        if len(out) < 1:
            if self.try_deprecated:
                out = api.get_packages_by_name(mod_name, return_deprecated=True)
                if len(out) < 1:
                    raise PackageMissing(mod_name)
                else:
                    msg = f"{mod_name} is deprecated, this may not work! Using latest version found"
                    warnings.warn(msg)
                    return sorted(out, key=lambda x: x.get_latest().date_created)[-1]
            else:
                raise PackageMissing(mod_name)
        elif len(out) > 1:
            if self.use_latest_date:
                warnings.warn(f"{mod_name} had multiple collision names, using one with latest date")
                return sorted(out, key=lambda x: x.get_latest().date_created)[-1] 
            else:
                raise ValueError(f"Got multiple versions/names for {mod}, try using full name instead")
        else:
            return out[0]

    def handle_dependencies(self, downloadable_mods):
        keys = [x["full_name"] for x in downloadable_mods]
        dependencies = []
        for mod in downloadable_mods:
            latest = mod.get_latest()
            dependencies.extend(latest.dependencies)
        #self.check_conflicting_versions(dependencies)
        dependencies.extend([
            x["full_name"] + "-" + x.get_latest().version_number for x in downloadable_mods
        ])
        self.check_conflicting_versions(dependencies)
        return dependencies

    def check_conflicting_versions(self, full_name_list: List[str], ignore=False):
        full_names = set(full_name_list)
        conflicts = Counter(["-".join(x.split('-')[:-1]) for x in full_names])
        return_set = set()
        for key, count in conflicts.items():
            if count > 1:
                corresponding_versions = {x for x in full_names if key in x}
                if not ignore:
                    raise ValueError(f"Found conflicting versions for {key}, got={corresponding_values}")

# Taken from online
def merge(scr_path, dir_path):
  files = next(os.walk(scr_path))[2]
  folders = next(os.walk(scr_path))[1]
  for file in files: # Copy the files
    scr_file = scr_path + "/" + file
    dir_file = dir_path + "/" + file
    if os.path.exists(dir_file): # Delete the old files if already exist
      os.remove(dir_file)
    shutil.copy(scr_file, dir_file)
  for folder in folders: # Merge again with the subdirectories
    scr_folder = scr_path + "/" + folder
    dir_folder = dir_path + "/" + folder
    if not os.path.exists(dir_folder): # Create the subdirectories if dont already exist
      os.mkdir(dir_folder)
    merge(scr_folder, dir_folder)
