# cdr.py
from __future__ import annotations
import struct
from typing import Any, Dict, List, Tuple, Type, Sequence, get_origin, get_args, Union, Annotated, NamedTuple

try:
    from pydantic import BaseModel
    _V2 = True
except Exception:  # pragma: no cover
    from pydantic import BaseModel  # type: ignore
    _V2 = False

# ---- Defaults for bare Python types (override if needed) ----
DEFAULT_INT  = "UInt32"   # choices: UInt8/UInt16/UInt32/UInt64/Int*/...
DEFAULT_FLOAT= "Float32"  # choices: Float32/Float64

class PrimMeta(NamedTuple):
    name: str
    fmt: str
    align: int
    is_bool: bool = False

Int8   = Annotated[int,   PrimMeta("Int8",   "b", 1)]
UInt8  = Annotated[int,   PrimMeta("UInt8",  "B", 1)]
Int16  = Annotated[int,   PrimMeta("Int16",  "h", 2)]
UInt16 = Annotated[int,   PrimMeta("UInt16", "H", 2)]
Int32  = Annotated[int,   PrimMeta("Int32",  "i", 4)]
UInt32 = Annotated[int,   PrimMeta("UInt32", "I", 4)]
Int64  = Annotated[int,   PrimMeta("Int64",  "q", 8)]
UInt64 = Annotated[int,   PrimMeta("UInt64", "Q", 8)]
Float32= Annotated[float, PrimMeta("Float32","f", 4)]
Float64= Annotated[float, PrimMeta("Float64","d", 8)]
Bool   = Annotated[bool,  PrimMeta("Bool",   "B", 1, True)]

_NAME2META = {
    "Int8":Int8.__metadata__[0], "UInt8":UInt8.__metadata__[0],
    "Int16":Int16.__metadata__[0], "UInt16":UInt16.__metadata__[0],
    "Int32":Int32.__metadata__[0], "UInt32":UInt32.__metadata__[0],
    "Int64":Int64.__metadata__[0], "UInt64":UInt64.__metadata__[0],
    "Float32":Float32.__metadata__[0], "Float64":Float64.__metadata__[0],
    "Bool":Bool.__metadata__[0],
}

def _get_prim_meta(t: Type[Any]) -> PrimMeta | None:
    if get_origin(t) is Annotated:
        base, *meta = get_args(t)
        for m in meta:
            if isinstance(m, PrimMeta):
                return m
    return None

class CDRReader:
    def __init__(self, data: bytes):
        self.buf = memoryview(data)
        self.off = 0
        self.le = False
        self.data_start = 0
        self._maybe_read_encapsulation()

    def _maybe_read_encapsulation(self):
        if len(self.buf) >= 4:
            enc = int.from_bytes(self.buf[0:2], "big")
            if enc in (0x0000, 0x0001):
                self.le = (enc == 0x0001)
                self.off = 4
                self.data_start = 4
                return
        self.le = True
        self.off = 0
        self.data_start = 0

    def _align(self, k: int):
        if k <= 1: return
        mis = (self.off - self.data_start) % k
        if mis: self.off += (k - mis)

    def _unpack(self, fmt: str) -> Any:
        size = struct.calcsize(fmt)
        end = self.off + size
        if end > len(self.buf): raise ValueError("CDR: buffer underrun")
        val = struct.unpack_from(fmt, self.buf, self.off)[0]
        self.off = end
        return val

    def read_primitive_meta(self, meta: PrimMeta) -> Any:
        self._align(meta.align)
        fmt = ("<" if self.le else ">") + meta.fmt
        v = self._unpack(fmt)
        return bool(v) if meta.is_bool else v

    def read_str(self) -> str:
        self._align(4)
        n = self.read_primitive_meta(_NAME2META["UInt32"])
        end = self.off + n
        if end > len(self.buf): raise ValueError("CDR: string overruns buffer")
        raw = bytes(self.buf[self.off:end]); self.off = end
        if raw and raw[-1] == 0: raw = raw[:-1]
        return raw.decode("utf-8", errors="strict")

    def read_bytes(self) -> bytes:
        self._align(4)
        n = self.read_primitive_meta(_NAME2META["UInt32"])
        end = self.off + n
        if end > len(self.buf): raise ValueError("CDR: bytes overrun")
        b = bytes(self.buf[self.off:end]); self.off = end
        return b

def _iter_model_fields(model_cls: Type[BaseModel]) -> List[tuple[str, Type[Any]]]:
    if _V2:
        fields = model_cls.model_fields  # type: ignore[attr-defined]
        return [(n, f.annotation) for n, f in fields.items()]
    fields = model_cls.__fields__  # type: ignore[attr-defined]
    return [(n, f.type_) for n, f in fields.items()]  # type: ignore

def _is_basemodel(t: Type[Any]) -> bool:
    try: return issubclass(t, BaseModel)  # type: ignore[arg-type]
    except Exception: return False

def _default_meta_for_python_type(t: Type[Any]) -> PrimMeta | None:
    if t is int:
        return _NAME2META[DEFAULT_INT]
    if t is float:
        return _NAME2META[DEFAULT_FLOAT]
    if t is bool:
        return _NAME2META["Bool"]
    return None

def _decode_t(reader: CDRReader, t: Type[Any]) -> Any:
    pm = _get_prim_meta(t)
    if pm is not None:
        return reader.read_primitive_meta(pm)

    # bare Python types -> defaults
    pm = _default_meta_for_python_type(t)
    if pm is not None:
        return reader.read_primitive_meta(pm)

    origin = get_origin(t)
    args = get_args(t)

    if origin is Union and type(None) in args:
        raise TypeError("Optional[T] not supported by raw CDR; add explicit presence flag.")

    if origin in (list, List, Sequence):
        (elem_t,) = args
        reader._align(4)
        length = reader.read_primitive_meta(_NAME2META["UInt32"])
        return [_decode_t(reader, elem_t) for _ in range(length)]

    if origin is tuple and args:
        if args[-1] is ...:
            raise TypeError("Ellipsis tuples not supported")
        return tuple(_decode_t(reader, at) for at in args)

    if _is_basemodel(t):
        return _decode_model(reader, t)  # type: ignore

    if t is str:   return reader.read_str()
    if t is bytes: return reader.read_bytes()
    if t is bytearray: return bytearray(reader.read_bytes())

    raise TypeError(f"Unsupported field type: {t}")

def _decode_model(reader: CDRReader, model_cls: Type[BaseModel]) -> BaseModel:
    values: Dict[str, Any] = {}
    for name, annot in _iter_model_fields(model_cls):
        values[name] = _decode_t(reader, annot)
    if _V2:
        return model_cls.model_validate(values)  # type: ignore[attr-defined]
    return model_cls.parse_obj(values)  # type: ignore[return-value]

def decode_cdr(model_cls: Type[BaseModel], data: bytes) -> BaseModel:
    reader = CDRReader(data)
    return _decode_model(reader, model_cls)
