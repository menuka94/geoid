""" CLasses for working with census Geoids

"""

__version__ = '0.0.1'
__author__ = "eric@civicknowledge.com"

summary_levels = { # (summary level value, base 10 chars,  Base 62 chars, prefix fields)
    'region' : (20,1,1,[]),
    'division' : (30,1,1,[]),
    'state' : (40,2,2,[]),
    'county' : (50,3,2,['state']),
    'cosub' : (60,5,3,['state','county']),
    'place' : (160,5,4,['state']),
    'ua': (400,5, 4, []),
    'tract' : (140,6,5,['state','county']),
    'blockgroup' : (150,1,1,['state','county','tract']), # Appears to always be the 1000's digit of block.
    'block' : (101,4,2,['state','county','tract']),
}


def base62_encode(num):
    """Encode a number in Base X. WIth the built-in alphabet, its base 62

    `num`: The number to encode
    `alphabet`: The alphabet to use for encoding
    Stolen from: http://stackoverflow.com/a/1119769/1144479
    """

    num = int(num)

    alphabet="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    if (num == 0):
        return alphabet[0]
    arr = []
    base = len(alphabet)
    while num:
        rem = num % base
        num = num // base
        arr.append(alphabet[rem])
    arr.reverse()
    return ''.join(arr)

def base62_decode(string):
    """Decode a Base X encoded string into the number

    Arguments:
    - `string`: The encoded string
    - `alphabet`: The alphabet to use for encoding
    Stolen from: http://stackoverflow.com/a/1119769/1144479
    """
    
    alphabet="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    base = len(alphabet)
    strlen = len(string)
    num = 0

    idx = 0
    for char in string:
        power = (strlen - (idx + 1))
        num += alphabet.index(char) * (base ** power)
        idx += 1

    return int(num)

import inspect,sys

def augment(module_name, base_class):
    """Call the augment() method for all of the derived classes in the module """

    for name, cls in inspect.getmembers(sys.modules[module_name],
                                        lambda x : inspect.isclass(x) and  issubclass(x, base_class) ):
        if cls == base_class:
            continue

        cls.augment()

def make_classes(base_class, module):
    """Create derived classes and put them into the same module as the base class.

    This function is called at the end of each of the derived calss modules, acs, census, civik and tiger.
    It will create a set of new derived class in the module, one for  each of the enries in the `summary_levels`
    dict.

    """

    all_classes_by_name = {}
    all_classes_by_sl = {}

    for k, v in summary_levels.items():

        cls = base_class.class_factory(k.capitalize())

        cls.augment()

        setattr(module, k.capitalize(), cls)


class Geoid(object):


    @classmethod
    def resolve_summary_level(cls, sl):
        try:
            return cls.sl_map[cls.encode.__func__(sl)][0]
        except KeyError:
            return None

    @classmethod
    def make_format_string(cls, level):
        sl_entry = summary_levels[level]

        segs = sl_entry[3] + [level]

        formats = [cls.sl_format] + [cls.elem_format.format(seg, summary_levels[seg][cls.width_pos]) for seg in segs]

        return ''.join(formats)

    @classmethod
    def make_regex(cls, level):

        sl_entry = summary_levels[level]

        segs = sl_entry[3] + [level]

        regexes = [cls.sl_regex] + [cls.elem_regex.format(seg, summary_levels[seg][cls.width_pos]) for seg in segs]

        re_str = '^' + ''.join(regexes) + "$"

        return re_str

    @classmethod
    def augment(cls):
        """Augment the class with computed formats, regexes, and other things. This caches these values so
        they don't have to be created for every instance. """

        import re

        level_name = cls.__name__.lower()

        sl_entry = summary_levels[level_name]

        cls.sl = sl_entry[0]

        cls.class_map[cls.__name__.lower()] = cls

        cls.sl_map[cls.sl] = (cls, sl_entry)

        cls.fmt = cls.make_format_string(cls.__name__.lower())

        cls.regex_str = cls.make_regex(cls.__name__.lower())
        cls.regex = re.compile(cls.regex_str)

        # List of field names
        cls.fields = sl_entry[3] + [level_name]

    @classmethod
    def get_class(cls, name_or_sl):
        """Return a derived calss based on the class name or the summar_level"""

        try:
            int(name_or_sl)

            return cls.sl_map[name_or_sl][0]

        except ValueError:

            return cls.class_map[name_or_sl.lower()]



    def __init__(self, *args, **kwargs):

        # This is a bit unusual, because it means, that , unlike nornal
        # python args, a kwarg can overwrite a position arg.

        d = dict(zip(self.fields, args))

        d.update(kwargs)

        for k, v in d.items():
            if k in self.fields:
                try:
                    setattr(self, k, v)
                except TypeError as e:
                    raise TypeError("Failed to convert '{}' ({}) for field '{}' in {}: {}"
                                    .format(v, type(v), k, type(self), e))
                except ValueError as e:
                    raise ValueError("Failed to convert '{}' ({}) for field '{}' in {}: {}"
                        .format(v, type(v), k, type(self), e))



    def __str__(self):

        d = self.__dict__
        d['sl'] = self.sl

        return self.fmt.format(**{ k:self.encode.__func__(v) for k,v in d.items() })

    @classmethod
    def parse(cls, gvid):

        if not cls.sl:
            sl = cls.decode.__func__(gvid[0:cls.sl_width])  # Civick and ACS include the SL, so can call from base type.

        else:
            sl = cls.sl # Otherwise must use derived class.


        cls, sl_entry = cls.sl_map[sl]

        m = cls.regex.match(gvid)

        if not m:
            raise Exception("Failed to match '{}' to '{}' ".format(gvid,cls.regex_str))

        d = m.groupdict()

        if not d:
            return None

        d = {k: cls.decode.__func__(v) for k, v in d.items()}

        try:
            del d['sl']
        except KeyError:
            pass

        return cls(**d)

    def convert(self,root_cls):
        """Convert to another derived class. cls is the base class for the derived type,
        ie AcsGeoid, TigerGeoid, etc. """

        d = self.__dict__
        d['sl'] = self.sl

        cls = root_cls.get_class(self.sl)

        return cls(**d)


def generate_all(sumlevel, d):
    """Generate a dict that includes all of the available geoid values, with keys
    for the most common names for those values. """

    from geoid.civick import GVid
    from geoid.tiger import TigerGeoid
    from geoid.acs import AcsGeoid

    d = dict(d.items())

    # Map common name variants
    if 'cousub' in d:
        d['cosub'] = d['cousub']
        del d['cousub']


    if 'blkgrp' in d:
        d['blockgroup'] = d['blkgrp']
        del d['blkgrp']



    gvid_class = GVid.resolve_summary_level(sumlevel)

    if not gvid_class:
        return {}

    geoidt_class = TigerGeoid.resolve_summary_level(sumlevel)
    geoid_class = AcsGeoid.resolve_summary_level(sumlevel)

    return dict(
        gvid = str(gvid_class(**d)),
        geoid = str(geoid_class(**d)),
        geoidt = str(geoidt_class(**d))
    )