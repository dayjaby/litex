import os
import jinja2

from litex.soc.doc.rst import reflow

def hex_zfill(v, size=None, upper=False):
    v = hex(v)
    if upper:
        v = v.upper()
    if size:
        v = "0x" + v[2:].zfill(size)
    return v

def strip_eventmanager_field(s):
    if s.startswith("ev_"):
        return s[3:]
    else:
        return s

def next_power_of_2(x, at_least=None):
    if at_least:
        return max([1<<(x-1).bit_length(), at_least])
    else:
        return 1<<(x-1).bit_length()

def get_ctype(size):
    return "uint{}_t".format(next_power_of_2(size, at_least=8))

class Environment(jinja2.Environment):
    def __init__(self, templates=[], *args, **kwargs):
        script_path = os.path.dirname(os.path.realpath(__file__))
        template_loaders = [
            jinja2.FileSystemLoader(path)
            for path in templates + [os.path.join(script_path, "templates")]
        ]
        super().__init__(
            loader=jinja2.ChoiceLoader(template_loaders),
            trim_blocks=True,
            lstrip_blocks=True,
            *args,
            **kwargs
        )

        self.filters["hex"] = hex_zfill
        self.filters["hasattr"] = hasattr
        self.filters["reflow"] = reflow
        self.filters["strip_eventmanager_field"] = strip_eventmanager_field
        self.globals["getattr"] = getattr
        self.globals["get_ctype"] = get_ctype
