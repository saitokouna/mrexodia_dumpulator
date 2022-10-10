from typing import Dict, Optional, Union, List

import pefile
from .memory import MemoryManager

# TODO: support forwards
class ModuleExport:
    def __init__(self, address: int, ordinal: int, name: str):
        self.address = address
        self.ordinal = ordinal
        self.name = name

class Module:
    def __init__(self, base: int, size: int, path: str):
        self.base = base
        self.size = size
        self.path = path
        self.name = path.split('\\')[-1]
        self.pe: pefile.PE = None
        self._exports_by_addr: Dict[int, int] = {}
        self._exports_by_name: Dict[str, int] = {}
        self.exports: List[ModuleExport] = []

    def parse_pe(self, pe: pefile.PE):
        self.pe = pe
        self.pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        pe_exports = pe.DIRECTORY_ENTRY_EXPORT.symbols if hasattr(pe, "DIRECTORY_ENTRY_EXPORT") else []
        for pe_export in pe_exports:
            va = self.base + pe_export.address
            if pe_export.name:
                name = pe_export.name.decode("ascii")
            else:
                name = None
            export = ModuleExport(va, pe_export.ordinal, name)
            self._exports_by_addr[va] = len(self.exports)
            if name is not None:
                self._exports_by_name[name] = len(self.exports)
            self.exports.append(export)

    def __repr__(self):
        return f"Module({hex(self.base)}, {hex(self.size)}, {repr(self.path)})"

    def __contains__(self, addr: int):
        return addr >= self.base and addr < self.base + self.size

class ModuleManager:
    def __init__(self, memory: MemoryManager):
        self._memory = memory
        self._name_lookup: Dict[str, int] = {}
        self._modules: Dict[int, Module] = {}

    def add(self, base: int, size: int, path: str):
        module = Module(base, size, path)
        self._modules[base] = module
        region = self._memory.find_region(module.base)
        assert region.start == base
        assert region is not None
        region.info = module
        self._name_lookup[module.name] = module.base
        self._name_lookup[module.name.lower()] = module.base
        self._name_lookup[module.path] = module.base
        return module

    def find(self, key: Union[str, int]) -> Optional[Module]:
        if isinstance(key, int):
            region = self._memory.find_region(key)
            if region.info:
                assert isinstance(region.info, Module)
                return region.info
            return None
        if isinstance(key, str):
            base = self._name_lookup.get(key, None)
            if base is None:
                return None
            return self.find(base)
        raise TypeError()

    def __getitem__(self, key: Union[str, int]) -> Module:
        module = self.find(key)
        if module is None:
            raise KeyError()
        return module

    def __iter__(self):
        for base in self._modules:
            yield self._modules[base]
