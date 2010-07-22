#!/usr/bin/env python
from xml.etree.cElementTree import *
from os.path import basename
import getopt
import sys
import re

# Jump to the bottom of this file for the main routine

# Some hacks to make the API more readable, and to keep backwards compability
_cname_re = re.compile('([A-Z0-9][a-z]+|[A-Z0-9]+(?![a-z])|[a-z]+)')
_cname_special_cases = {'DECnet':'decnet'}

_extension_special_cases = ['XPrint', 'XCMisc', 'BigRequests']

_cplusplus_annoyances = {'class' : '_class',
                         'new'   : '_new',
                         'delete': '_delete'}

_hlines = []
_hlevel = 0
_clines = []
_clevel = 0
_ns = None

# global variable to keep track of serializers
# due to weird dependencies, I see no way to do this more elegant at the moment
finished_serializers = []

def _h(fmt, *args):
    '''
    Writes the given line to the header file.
    '''
    _hlines[_hlevel].append(fmt % args)
    
def _c(fmt, *args):
    '''
    Writes the given line to the source file.
    '''
    _clines[_clevel].append(fmt % args)
    
def _hc(fmt, *args):
    '''
    Writes the given line to both the header and source files.
    '''
    _h(fmt, *args)
    _c(fmt, *args)

# XXX See if this level thing is really necessary.
def _h_setlevel(idx):
    '''
    Changes the array that header lines are written to.
    Supports writing different sections of the header file.
    '''
    global _hlevel
    while len(_hlines) <= idx:
        _hlines.append([])
    _hlevel = idx
    
def _c_setlevel(idx):
    '''
    Changes the array that source lines are written to.
    Supports writing to different sections of the source file.
    '''
    global _clevel
    while len(_clines) <= idx:
        _clines.append([])
    _clevel = idx
    
def _n_item(str):
    '''
    Does C-name conversion on a single string fragment.
    Uses a regexp with some hard-coded special cases.
    '''
    if str in _cname_special_cases:
        return _cname_special_cases[str]
    else:
        split = _cname_re.finditer(str)
        name_parts = [match.group(0) for match in split]
        return '_'.join(name_parts)
    
def _cpp(str):
    '''
    Checks for certain C++ reserved words and fixes them.
    '''
    if str in _cplusplus_annoyances:
        return _cplusplus_annoyances[str]
    else:
        return str

def _ext(str):
    '''
    Does C-name conversion on an extension name.
    Has some additional special cases on top of _n_item.
    '''
    if str in _extension_special_cases:
        return _n_item(str).lower()
    else:
        return str.lower()
    
def _n(list):
    '''
    Does C-name conversion on a tuple of strings.
    Different behavior depending on length of tuple, extension/not extension, etc.
    Basically C-name converts the individual pieces, then joins with underscores.
    '''
    if len(list) == 1:
        parts = list
    elif len(list) == 2:
        parts = [list[0], _n_item(list[1])]
    elif _ns.is_ext:
        parts = [list[0], _ext(list[1])] + [_n_item(i) for i in list[2:]]
    else:
        parts = [list[0]] + [_n_item(i) for i in list[1:]]
    return '_'.join(parts).lower()

def _t(list):
    '''
    Does C-name conversion on a tuple of strings representing a type.
    Same as _n but adds a "_t" on the end.
    '''
    if len(list) == 1:
        parts = list
    elif len(list) == 2:
        parts = [list[0], _n_item(list[1]), 't']
    elif _ns.is_ext:
        parts = [list[0], _ext(list[1])] + [_n_item(i) for i in list[2:]] + ['t']
    else:
        parts = [list[0]] + [_n_item(i) for i in list[1:]] + ['t']
    return '_'.join(parts).lower()
        

def c_open(self):
    '''
    Exported function that handles module open.
    Opens the files and writes out the auto-generated comment, header file includes, etc.
    '''
    global _ns
    _ns = self.namespace
    _ns.c_ext_global_name = _n(_ns.prefix + ('id',))

    # Build the type-name collision avoidance table used by c_enum
    build_collision_table()

    _h_setlevel(0)
    _c_setlevel(0)

    _hc('/*')
    _hc(' * This file generated automatically from %s by c_client.py.', _ns.file)
    _hc(' * Edit at your peril.')
    _hc(' */')
    _hc('')

    _h('/**')
    _h(' * @defgroup XCB_%s_API XCB %s API', _ns.ext_name, _ns.ext_name)
    _h(' * @brief %s XCB Protocol Implementation.', _ns.ext_name)
    _h(' * @{')
    _h(' **/')
    _h('')
    _h('#ifndef __%s_H', _ns.header.upper())
    _h('#define __%s_H', _ns.header.upper())
    _h('')
    _h('#include "xcb.h"')

    _c('#include <stdlib.h>')
    _c('#include <string.h>')
    _c('#include <assert.h>')
    _c('#include "xcbext.h"')
    _c('#include "%s.h"', _ns.header)
        
    if _ns.is_ext:
        for (n, h) in self.imports:
            _hc('#include "%s.h"', h)

    _h('')
    _h('#ifdef __cplusplus')
    _h('extern "C" {')
    _h('#endif')

    if _ns.is_ext:
        _h('')
        _h('#define XCB_%s_MAJOR_VERSION %s', _ns.ext_name.upper(), _ns.major_version)
        _h('#define XCB_%s_MINOR_VERSION %s', _ns.ext_name.upper(), _ns.minor_version)
        _h('  ') #XXX
        _h('extern xcb_extension_t %s;', _ns.c_ext_global_name)

        _c('')
        _c('xcb_extension_t %s = { "%s", 0 };', _ns.c_ext_global_name, _ns.ext_xname)

def c_close(self):
    '''
    Exported function that handles module close.
    Writes out all the stored content lines, then closes the files.
    '''
    _h_setlevel(2)
    _c_setlevel(2)
    _hc('')

    _h('')
    _h('#ifdef __cplusplus')
    _h('}')
    _h('#endif')

    _h('')
    _h('#endif')
    _h('')
    _h('/**')
    _h(' * @}')
    _h(' */')

    # Write header file
    hfile = open('%s.h' % _ns.header, 'w')
    for list in _hlines:
        for line in list:
            hfile.write(line)
            hfile.write('\n')
    hfile.close()

    # Write source file
    cfile = open('%s.c' % _ns.header, 'w')
    for list in _clines:
        for line in list:
            cfile.write(line)
            cfile.write('\n')
    cfile.close()

def build_collision_table():
    global namecount
    namecount = {}

    for v in module.types.values():
        name = _t(v[0])
        namecount[name] = (namecount.get(name) or 0) + 1

def c_enum(self, name):
    '''
    Exported function that handles enum declarations.
    '''

    tname = _t(name)
    if namecount[tname] > 1:
        tname = _t(name + ('enum',))

    _h_setlevel(0)
    _h('')
    _h('typedef enum %s {', tname)

    count = len(self.values)

    for (enam, eval) in self.values:
        count = count - 1
        equals = ' = ' if eval != '' else ''
        comma = ',' if count > 0 else ''
        _h('    %s%s%s%s', _n(name + (enam,)).upper(), equals, eval, comma)

    _h('} %s;', tname)

def _c_type_setup(self, name, postfix):
    '''
    Sets up all the C-related state by adding additional data fields to
    all Field and Type objects.  Here is where we figure out most of our
    variable and function names.

    Recurses into child fields and list member types.
    '''
    # Do all the various names in advance
    self.c_type = _t(name + postfix)
    self.c_wiretype = 'char' if self.c_type == 'void' else self.c_type

    self.c_iterator_type = _t(name + ('iterator',))
    self.c_next_name = _n(name + ('next',))
    self.c_end_name = _n(name + ('end',))

    self.c_request_name = _n(name)
    self.c_checked_name = _n(name + ('checked',))
    self.c_unchecked_name = _n(name + ('unchecked',))
    self.c_reply_name = _n(name + ('reply',))
    self.c_reply_type = _t(name + ('reply',))
    self.c_cookie_type = _t(name + ('cookie',))

    self.c_aux_name = _n(name + ('aux',))
    self.c_aux_checked_name = _n(name + ('aux', 'checked'))
    self.c_aux_unchecked_name = _n(name + ('aux', 'unchecked'))
    self.c_serialize_name = _n(name + ('serialize',))
    self.c_unserialize_name = _n(name + ('unserialize',))
    if hasattr(self, 'reply'):
        if self.reply is not None:
            self.c_serialize_name = _n(name + ('reply', 'serialize'))
            self.c_unserialize_name = _n(name + ('reply', 'unserialize'))

    # whether a request or reply has a switch field
    self.need_aux = False
    self.need_serialize = False
    if self.is_switch:
        self.need_serialize = True
        for bitcase in self.bitcases:
            _c_type_setup(bitcase.type, bitcase.field_type, ())

    if self.is_container:

        self.c_container = 'union' if self.is_union else 'struct'
        prev_varsized_field = None
        prev_varsized_offset = 0
        first_field_after_varsized = None

        for field in self.fields:
            _c_type_setup(field.type, field.field_type, ())
            if field.type.is_list:
                _c_type_setup(field.type.member, field.field_type, ())
                # FIXME - structures with variable sized members, sort out when serialize() is needed
                if (field.type.nmemb is None): # and not field.type.member.fixed_size():
                    self.need_serialize = True

            field.c_field_type = _t(field.field_type)
            field.c_field_const_type = ('' if field.type.nmemb == 1 else 'const ') + field.c_field_type
            field.c_field_name = _cpp(field.field_name)
            field.c_subscript = '[%d]' % field.type.nmemb if (field.type.nmemb > 1) else ''
            field.c_pointer = ' ' if field.type.nmemb == 1 else '*'
            if field.type.is_switch:
                field.c_pointer = '*'
                field.c_field_const_type = 'const ' + field.c_field_type
                self.need_aux = True

            field.c_iterator_type = _t(field.field_type + ('iterator',))      # xcb_fieldtype_iterator_t
            field.c_iterator_name = _n(name + (field.field_name, 'iterator')) # xcb_container_field_iterator
            field.c_accessor_name = _n(name + (field.field_name,))            # xcb_container_field
            field.c_length_name = _n(name + (field.field_name, 'length'))     # xcb_container_field_length
            field.c_end_name = _n(name + (field.field_name, 'end'))           # xcb_container_field_end

            field.prev_varsized_field = prev_varsized_field
            field.prev_varsized_offset = prev_varsized_offset

            if prev_varsized_offset == 0:
                first_field_after_varsized = field
            field.first_field_after_varsized = first_field_after_varsized

            if field.type.fixed_size():
                prev_varsized_offset += field.type.size
            else:
                self.last_varsized_field = field
                prev_varsized_field = field
                prev_varsized_offset = 0                    

    # as switch does never appear at toplevel, 
    # continue here with type construction
    if self.is_switch:
        # special: switch C structs get pointer fields for variable-sized members
        _c_complex(self)
        # FIXME: declare switch (un)packing functions
        _c_accessors(self, name, name)

    # FIXME - in case of request/reply, serialize() is not always needed
    if self.need_serialize and not self.is_bitcase:
        if self.c_serialize_name not in finished_serializers:
            _c_serialize(self)
            _c_unserialize(self)
            finished_serializers.append(self.c_serialize_name)
# _c_type_setup()

def get_request_fields(self):
    param_fields = []
    wire_fields = []

    for field in self.fields:
        if field.visible:
            # the field should appear as a parameter in the function call
            param_fields.append(field)
        if field.wire and not field.auto:
            if field.type.fixed_size() and not self.is_switch:
                # field in the xcb_out structure
                wire_fields.append(field)
        # fields like 'pad0' are skipped!
                    
    return (param_fields, wire_fields)
# get_request_fields()

def get_switch_expr_fields(self):
    # get the fields referenced by the switch expression
    def get_expr_fields(expr):
        if expr.op is None:
            if expr.lenfield_name is not None:
                return [expr.lenfield_name]
        else:
            if expr.op == '~':
                return get_expr_fields(expr.rhs)
            elif expr.op == 'popcount':
                return get_expr_fields(expr.rhs)
            elif expr.op == 'sumof':
                return [expr.lenfield_name]
            elif expr.op == 'enumref':
                return []
            else: 
                return get_expr_fields(expr.lhs) + get_expr_fields(expr.rhs)
    # get_expr_fields()
    
    # resolve the field names with the parent structure(s)
    unresolved_fields = get_expr_fields(self.expr)
    expr_fields = dict.fromkeys(unresolved_fields)
    for p in reversed(self.parent):
        parent_fields = dict((f.field_name, f) for f in p.fields)
        for f in parent_fields.keys():
            if f in unresolved_fields:
                expr_fields[f] = parent_fields[f]
                unresolved_fields.remove(f)
        if len(unresolved_fields) == 0:
            break
                
    if None in expr_fields.values():
        raise Exception("could not resolve all fields for <switch> %s" % self.name)

    params = expr_fields.values()
    return params
# get_switch_expr_fields()

def get_serialize_params(context, self, buffer_var='_buffer', aux_var='_aux'):
    param_fields, wire_fields = get_request_fields(self)
    if self.is_switch:
        param_fields = get_switch_expr_fields(self)

    # _serialize function parameters
    if  'serialize' == context:
        params = [('void', '**', buffer_var)]
    elif 'unserialize' == context:
        params = [('const void', '*', buffer_var)]

    # make sure all required length fields are present
    for p in param_fields:
        if p.visible and not p.wire and not p.auto:
            typespec = p.c_field_type
            pointerspec = ''
            params.append((typespec, pointerspec, p.c_field_name))

    # parameter fields if any
    if self.is_switch:
        for p in get_switch_expr_fields(self):
            typespec = p.c_field_const_type
            pointerspec = p.c_pointer
            params.append((typespec, pointerspec, p.c_field_name))
  
    # aux argument - structure to be serialized
    if 'serialize' == context:
        params.append(('const %s' % self.c_type, '*', aux_var))
    elif 'unserialize' == context and self.is_switch:
        params.append(('%s' % self.c_type, '*', aux_var))
    if not self.is_switch and 'serialize' == context:
        for p in param_fields:
            if not p.type.fixed_size():
                params.append((p.c_field_const_type, p.c_pointer, p.c_field_name))
    return (param_fields, wire_fields, params)
# get_serialize_params()

def _c_field_mapping(context, complex_type):
    def get_prefix(field):
        prefix = ''
        if context in ('serialize', 'unserialize'):
            if field.type.fixed_size() or complex_type.is_switch:
                prefix = '_aux->'
        else:
            raise Exception("unknown context '%s' in c_field_mapping" % context)
        return prefix
    # get_prefix()
    def get_field_name(fields, complex_type, prefix=''):
        for f in complex_type.fields:
            if '' == prefix:
                prefix = get_prefix(f)

            fname = "%s%s" % (prefix, f.c_field_name)
            if fields.has_key(f.field_name):
                continue
                raise Exception("field name %s has been registered before" % f.field_name)
            fields[f.field_name] = (fname, f)
            if f.type.is_container:
                new_prefix = "%s%s" % (prefix, f.c_field_name)
                new_prefix += "." if f.type.is_switch else "->"
                get_field_name(fields, f.type, new_prefix)
    # get_field_name()

    # dict(field_name : (c_field_name, field))
    fields = {}
    get_field_name(fields, complex_type)
    
    # switch: get the fields referenced by the switch expr as well
    #         these may not belong to any structure
    if complex_type.is_switch:
        pass
#       FIXME: fields += get_serialize_params(context, complex_type)

    return fields
# _c_field_mapping()

def _c_serialize_helper_prefix(prefix):
    prefix_str = prefix
    lenfield_prefix = "_aux"
    if prefix != '':
        prefix_str += "->"
        lenfield_prefix += "->%s" % prefix
    return (prefix_str, lenfield_prefix)
# _c_serialize_helper_prefix

def _c_serialize_helper_insert_padding(context, code_lines, space):
    code_lines.append('%s    xcb_buffer_len += xcb_block_len;' % space)
    code_lines.append('%s    /* padding */' % space)
    code_lines.append('%s    xcb_pad = -xcb_block_len & 3;' % space)
    code_lines.append('%s    if (0 != xcb_pad) {' % space)

    if 'serialize' == context:
        code_lines.append('%s        xcb_parts[xcb_parts_idx].iov_base = xcb_pad0;' % space)
        code_lines.append('%s        xcb_parts[xcb_parts_idx].iov_len = xcb_pad;' % space)
        code_lines.append('%s        xcb_parts_idx++;' % space)
    elif 'unserialize' == context:
        code_lines.append('%s        xcb_tmp += xcb_pad;' % space)

    code_lines.append('%s        xcb_buffer_len += xcb_pad;' % space)    
    code_lines.append('%s        xcb_pad = 0;' % space)
    code_lines.append('%s    }' % space)
    code_lines.append('%s    xcb_block_len = 0;' % space)
    
    return 1
# _c_serialize_helper_insert_padding()

def _c_serialize_helper_switch(context, self, complex_name, 
                               code_lines, temp_vars, 
                               space, prefix):
    count = 0
    prefix_str, lenfield_prefix = _c_serialize_helper_prefix(prefix)
    switch_expr = _c_accessor_get_expr(self.expr)

    for b in self.bitcases:            
        bitcase_expr = _c_accessor_get_expr(b.type.expr, prefix)
        code_lines.append('    if(%s & %s) {' % (switch_expr, bitcase_expr))

        _c_serialize_helper_fields(context, b.type, 
                                   code_lines, temp_vars, 
                                   space="%s    " % space, 
                                   prefix="%s%s" % (prefix_str, complex_name), 
                                   is_bitcase = True)
        code_lines.append('    }')

    if 'serialize' == context:
        count = _c_serialize_helper_insert_padding(context, code_lines, space)
    if 'unserialize' == context:
        # padding
        code_lines.append('%s    xcb_pad = -xcb_block_len & 3;' % space)
        code_lines.append('%s    xcb_buffer_len += xcb_block_len + xcb_pad;' % space)
    
    return count
# _c_serialize_helper_switch

def _c_serialize_helper_switch_field(self, field):
    # switch is handled by this function as a special case
    args = get_switch_expr_fields(field.type)
    field_mapping = _c_field_mapping('unserialize', self)
    c_field_names = ''
    for a in args:
        c_field_names += "%s, " % field_mapping[a.field_name][0]
    switch_field_name = field_mapping[field.field_name][0]
    length = "%s(xcb_tmp, %s&%s)" % (field.type.c_unserialize_name, 
                                     c_field_names, switch_field_name)
    return length
# _c_serialize_helper_switch_field()

def _c_serialize_helper_list_field(context, self, field, 
                                   code_lines, temp_vars, 
                                   space, prefix):
    """
    helper function for (un)serialize to cope with lists of variable length
    """
    expr = field.type.expr
    prefix_str, lenfield_prefix = _c_serialize_helper_prefix(prefix)
    param_fields, wire_fields, params = get_serialize_params('unserialize', self)
    param_names = [p[2] for p in params]

    # look if the list's lenfield is a struct member or a function argument
    # special case: if the list has a length field, its name will returned 
    # unchanged by calling c_accessor_get_length(expr)
    if expr.lenfield_name == _c_accessor_get_length(expr):
        if expr.lenfield_name in param_names:
            # the length field appears as separate argument in unserialize, 
            # so no need for a prefix
            lenfield_prefix = ''
    list_length = _c_accessor_get_expr(expr, lenfield_prefix)

    # default: list with fixed size elements
    length = '%s * sizeof(%s)' % (list_length, field.type.member.c_wiretype)
    # list with variable-sized elements 
    if field.type.size is None:
        length = ''
        if 'unserialize' == context:
            temp_vars.add('    unsigned int i;')
            temp_vars.add('    unsigned int xcb_tmp_len;')
            code_lines.append("%s    for(i=0; i<%s; i++) {" % (space, list_length))
            code_lines.append("%s        xcb_tmp_len = %s(xcb_tmp);" % 
                              (space, field.type.c_unserialize_name))
            code_lines.append("%s        xcb_block_len += xcb_tmp_len;" % space)
            code_lines.append("%s        xcb_tmp += xcb_tmp_len;" % space)
            code_lines.append("%s    }" % space)                        
        elif 'serialize' == context:
            code_lines.append('%s    xcb_parts[xcb_parts_idx].iov_len = 0;' % space)
            code_lines.append('%s    xcb_tmp = (char *) %s%s;' % (space, prefix_str, field.c_field_name))
            code_lines.append('%s    for(i=0; i<%s; i++) {' 
                              % (space, _c_accessor_get_expr(expr, lenfield_prefix)))
            code_lines.append('%s        xcb_block_len = %s(xcb_tmp);' % (space, field.type.c_unserialize_name))
            code_lines.append('%s        xcb_parts[xcb_parts_idx].iov_len += xcb_block_len;' % space)
            code_lines.append('%s    }' % space)
            code_lines.append('%s    xcb_block_len = xcb_parts[xcb_parts_idx].iov_len;' % space)
            
    return length
# _c_serialize_helper_list_field()

def _c_serialize_helper_fields_fixed_size(context, self, field, 
                                          code_lines, temp_vars, 
                                          space, prefix):
    prefix_str, lenfield_prefix = _c_serialize_helper_prefix(prefix)
    code_lines.append('%s    /* %s.%s */' % (space, self.c_type, field.c_field_name))

    length = "sizeof(%s)" % field.c_field_type

    if 'unserialize' == context:
        value = '    _aux->%s = *(%s *)xcb_tmp;' % (field.c_field_name, field.c_field_type) 
        # FIXME? - lists
        if field.type.is_list:
            raise Exception('list with fixed number of elemens unhandled in _unserialize()')
    elif 'serialize' == context:
        value = '    xcb_parts[xcb_parts_idx].iov_base = (char *) ' 

        if field.type.is_expr:
            # need to register a temporary variable for the expression
            if field.type.c_type is None:
                raise Exception("type for field '%s' (expression '%s') unkown" % 
                                (field.field_name, _c_accessor_get_expr(field.type.expr)))
            temp_vars.add('    %s xcb_expr_%s = %s;' % (field.type.c_type, field.field_name, 
                                                        _c_accessor_get_expr(field.type.expr, prefix)))
            value += "&xcb_expr_%s;" % field.field_name 

        elif field.type.is_pad:
            if field.type.nmemb == 1:
                value += "&xcb_pad;"
            else:
                value = '    memset(xcb_parts[xcb_parts_idx].iov_base, 0, %d);' % field.type.nmemb
                length += "*%d" % field.type.nmemb

        else:
            # non-list type with fixed size
            if field.type.nmemb == 1:
                value += "&%s%s;" % (prefix_str, field.c_field_name)
            # list with nmemb (fixed size) elements
            else:
                value += '%s%s;' % (prefix_str, field.c_field_name)
                length = '%d' % field.type.nmemb

    return (value, length)
# _c_serialize_helper_fields_fixed_size()

def _c_serialize_helper_fields_variable_size(context, self, field, 
                                             code_lines, temp_vars, 
                                             space, prefix):
    prefix_str, lenfield_prefix = _c_serialize_helper_prefix(prefix)

    if 'unserialize' == context:
        value = ''
    elif 'serialize' == context:
        value = '    xcb_parts[xcb_parts_idx].iov_base = (char *) %s%s;' % (prefix_str, field.c_field_name)
    length = ''

    prefix_str, lenfield_prefix = _c_serialize_helper_prefix(prefix)
    code_lines.append('%s    /* %s */' % (space, field.c_field_name))

    if field.type.is_list:
        length = _c_serialize_helper_list_field(context, self, field, 
                                                code_lines, temp_vars, 
                                                space, prefix)
    elif field.type.is_switch:
        length = _c_serialize_helper_switch_field(self, field)
    else:
        length = "%s(xcb_tmp)" % (field.type.c_unserialize_name)

    return (value, length)
# _c_serialize_helper_fields_variable_size

def _c_serialize_helper_fields(context, self, 
                               code_lines, temp_vars, 
                               space, prefix, is_bitcase):
    count = 0
    need_padding = False
    prefix_str, lenfield_prefix = _c_serialize_helper_prefix(prefix)

    for field in self.fields:
        if not ((field.wire and not field.auto) or field.visible):
            continue

        # switch/bitcase: fixed size fields must be considered explicitly 
        if field.type.fixed_size():
            if is_bitcase:
                value, length = _c_serialize_helper_fields_fixed_size(context, self, field, 
                                                                      code_lines, temp_vars, 
                                                                      space, prefix)
            else:
                continue

        # fields with variable size
        else:
            # switch/bitcase: always calculate padding before and after variable sized fields
            if need_padding or is_bitcase:
                _c_serialize_helper_insert_padding(context, code_lines, space)

            value, length = _c_serialize_helper_fields_variable_size(context, self, field, 
                                                                     code_lines, temp_vars, 
                                                                     space, prefix)
                
        # save (un)serialization C code
        if '' != value:
            code_lines.append('%s%s' % (space, value))
        if field.type.fixed_size() and is_bitcase:
            code_lines.append('%s    xcb_block_len += %s;' % (space, length))
            if 'unserialize' == context:
                code_lines.append('%s    xcb_tmp += %s;' % (space, length))
        else:
            # padding
            if '' != length:
                code_lines.append('%s    xcb_block_len = %s;' % (space, length))
                if 'unserialize' == context:
                    code_lines.append('%s    xcb_tmp += xcb_block_len;' % space)
        if 'serialize' == context:
            if '' != length:
                code_lines.append('%s    xcb_parts[xcb_parts_idx].iov_len = xcb_block_len;' % space)
            code_lines.append('%s    xcb_parts_idx++;' % space)
            count += 1
        need_padding = True
        
    return count
# _c_serialize_helper_fields()    

def _c_serialize_helper(context, complex_type, 
                        code_lines, temp_vars, 
                        space='', prefix=''):
    count = 0
    if hasattr(complex_type, 'type'):
        self = complex_type.type
        complex_name = complex_type.name
    else:
        self = complex_type
        complex_name = '_aux'

    # special case: switch is serialized by evaluating each bitcase separately
    if self.is_switch:
        count += _c_serialize_helper_switch(context, self, complex_name, 
                                            code_lines, temp_vars, 
                                            space, prefix)

    # all other data types can be evaluated one field a time
    else: 
        # unserialize & fixed size fields: simply cast the buffer to the respective xcb_out type
        if 'unserialize' == context:
            code_lines.append('%s    xcb_block_len += sizeof(%s);' % (space, self.c_type))
            code_lines.append('%s    xcb_tmp += xcb_block_len;' % space)
            _c_serialize_helper_insert_padding(context, code_lines, space)

        count += _c_serialize_helper_fields(context, self, 
                                            code_lines, temp_vars, 
                                            space, prefix, False)
        # "final padding"
        count += _c_serialize_helper_insert_padding(context, code_lines, space)

    return count    
# _c_serialize_helper()

def _c_serialize(self):
    _h_setlevel(1)
    _c_setlevel(1)

    _hc('')
    # _serialize() returns the buffer size
    _hc('int')

    variable_size_fields = 0
    # maximum space required for type definition of function arguments
    maxtypelen = 0
    param_fields, wire_fields, params = get_serialize_params('serialize', self)

    # determine N(variable_fields) 
    for field in param_fields:
        # if self.is_switch, treat all fields as if they are variable sized
        if not field.type.fixed_size() or self.is_switch:
            variable_size_fields += 1
    # determine maxtypelen
    for p in params:
        maxtypelen = max(maxtypelen, len(p[0]) + len(p[1]))    

    # write to .c/.h
    for p in range(len(params)):
        line = ""
        typespec, pointerspec, field_name = params[p]
        indent = ' '*(len(self.c_serialize_name)+2)
        # p==0: function declaration
        if 0==p:
            line = "%s (" % self.c_serialize_name
            indent = ''
        spacing = ' '*(maxtypelen-len(typespec)-len(pointerspec))
        line += "%s%s%s  %s%s  /**< */" % (indent, typespec, spacing, pointerspec, field_name)
        if p < len(params)-1:
            _hc("%s," % line)
        else:
            _h("%s);" % line)
            _c("%s)" % line)
                
    _c('{')
    if not self.is_switch:
        _c('    %s *xcb_out = *_buffer;', self.c_type)
        _c('    unsigned int xcb_out_pad = -sizeof(%s) & 3;', self.c_type)
        _c('    unsigned int xcb_buffer_len = sizeof(%s) + xcb_out_pad;', self.c_type)
    else:
        _c('    char *xcb_out = *_buffer;')
        _c('    unsigned int xcb_buffer_len = 0;')
    if variable_size_fields > 0:        
        code_lines = []
        temp_vars = set()
        count =_c_serialize_helper('serialize', self, 
                                   code_lines, temp_vars)
        # update variable size fields 
        variable_size_fields = count
        temp_vars.add('    unsigned int xcb_pad = 0;')
        temp_vars.add('    char xcb_pad0[3] = {0, 0, 0};') 
        temp_vars.add('    struct iovec xcb_parts[%d];' % (count+1))
        temp_vars.add('    unsigned int xcb_parts_idx = 0;')
        temp_vars.add('    unsigned int xcb_block_len = 0;')
        temp_vars.add('    unsigned int i;')
        temp_vars.add('    char *xcb_tmp;')
        for t in temp_vars:
            _c(t)

    _c('')
    
    if variable_size_fields > 0:        
        for l in code_lines:
            _c(l)
    _c('')

    # variable sized fields have been collected, now
    # allocate memory and copy everything into a continuous memory area
    _c('    if (NULL == xcb_out) {')
    _c('        /* allocate memory  */')
    _c('        *_buffer = malloc(xcb_buffer_len);')
    _c('        xcb_out = *_buffer;')
    _c('    }')
    _c('')

    # fill in struct members
    if not self.is_switch:
        if len(wire_fields)>0:
            _c('    *xcb_out = *_aux;')

    # copy variable size fields into the buffer
    if variable_size_fields > 0:
        # xcb_out padding
        if not self.is_switch:
            _c('    xcb_tmp = (char*)++xcb_out;')
            _c('    xcb_tmp += xcb_out_pad;')
        else:
            _c('    xcb_tmp = xcb_out;')
            
        # variable sized fields
        _c('    for(i=0; i<xcb_parts_idx; i++) {')
        _c('        memcpy(xcb_tmp, xcb_parts[i].iov_base, xcb_parts[i].iov_len);')
        _c('        xcb_tmp += xcb_parts[i].iov_len;')
        _c('    }')
    _c('')
    _c('    return xcb_buffer_len;')
    _c('}')
# _c_serialize()

def _c_unserialize(self):
    _h_setlevel(1)
    _c_setlevel(1)

    # _unserialize()
    _hc('')
    # _unserialize() returns the buffer size as well
    _hc('int')


    variable_size_fields = 0
    # maximum space required for type definition of function arguments
    maxtypelen = 0
    param_fields, wire_fields, params = get_serialize_params('unserialize', self)

    # determine N(variable_fields) 
    for field in param_fields:
        # if self.is_switch, treat all fields as if they are variable sized
        if not field.type.fixed_size() or self.is_switch:
            variable_size_fields += 1
    # determine maxtypelen
    for p in params:
        maxtypelen = max(maxtypelen, len(p[0]) + len(p[1]))    

    # write to .c/.h
    for p in range(len(params)):
        line = ""
        typespec, pointerspec, field_name = params[p]
        indent = ' '*(len(self.c_unserialize_name)+2)
        # p==0: function declaration
        if 0==p:
            line = "%s (" % self.c_unserialize_name
            indent = ''
        spacing = ' '*(maxtypelen-len(typespec)-len(pointerspec))
        line += "%s%s%s %s%s  /**< */" % (indent, typespec, spacing, pointerspec, field_name)
        if p < len(params)-1:
            _hc("%s," % line)
        else:
            _h("%s);" % line)
            _c("%s)" % line)
                
    _c('{')
    _c('    char *xcb_tmp = (char *)_buffer;')
    if not self.is_switch:
        _c('    const %s *_aux = (%s *)_buffer;', self.c_type, self.c_type)
    _c('    unsigned int xcb_buffer_len = 0;')
    _c('    unsigned int xcb_block_len = 0;')
    _c('    unsigned int xcb_pad = 0;')

    code_lines = []
    temp_vars = set()
    _c_serialize_helper('unserialize', self, 
                        code_lines, temp_vars)
    for t in temp_vars:
        _c(t)
    _c('')

    for l in code_lines:
        _c(l)
    _c('')
    _c('    return xcb_buffer_len;')
    _c('}')
# _c_unserialize()

def _c_iterator_get_end(field, accum):
    '''
    Figures out what C code is needed to find the end of a variable-length structure field.
    For nested structures, recurses into its last variable-sized field.
    For lists, calls the end function
    '''
    if field.type.is_container:
        accum = field.c_accessor_name + '(' + accum + ')'
        # XXX there could be fixed-length fields at the end
        return _c_iterator_get_end(field.type.last_varsized_field, accum)
    if field.type.is_list:
        # XXX we can always use the first way
        if field.type.member.is_simple:
            return field.c_end_name + '(' + accum + ')'
        else:
            return field.type.member.c_end_name + '(' + field.c_iterator_name + '(' + accum + '))'

def _c_iterator(self, name):
    '''
    Declares the iterator structure and next/end functions for a given type.
    '''
    _h_setlevel(0)
    _h('')
    _h('/**')
    _h(' * @brief %s', self.c_iterator_type)
    _h(' **/')
    _h('typedef struct %s {', self.c_iterator_type)
    _h('    %s *data; /**<  */', self.c_type)
    _h('    int%s rem; /**<  */', ' ' * (len(self.c_type) - 2))
    _h('    int%s index; /**<  */', ' ' * (len(self.c_type) - 2))
    _h('} %s;', self.c_iterator_type)

    _h_setlevel(1)
    _c_setlevel(1)
    _h('')
    _h('/**')
    _h(' * Get the next element of the iterator')
    _h(' * @param i Pointer to a %s', self.c_iterator_type)
    _h(' *')
    _h(' * Get the next element in the iterator. The member rem is')
    _h(' * decreased by one. The member data points to the next')
    _h(' * element. The member index is increased by sizeof(%s)', self.c_type)
    _h(' */')
    _c('')
    _hc('')
    _hc('/*****************************************************************************')
    _hc(' **')
    _hc(' ** void %s', self.c_next_name)
    _hc(' ** ')
    _hc(' ** @param %s *i', self.c_iterator_type)
    _hc(' ** @returns void')
    _hc(' **')
    _hc(' *****************************************************************************/')
    _hc(' ')
    _hc('void')
    _h('%s (%s *i  /**< */);', self.c_next_name, self.c_iterator_type)
    _c('%s (%s *i  /**< */)', self.c_next_name, self.c_iterator_type)
    _c('{')

    if not self.fixed_size():
        _c('    %s *R = i->data;', self.c_type)
        _c('    xcb_generic_iterator_t child = %s;', _c_iterator_get_end(self.last_varsized_field, 'R'))
        _c('    --i->rem;')
        _c('    i->data = (%s *) child.data;', self.c_type)
        _c('    i->index = child.index;')
    else:
        _c('    --i->rem;')
        _c('    ++i->data;')
        _c('    i->index += sizeof(%s);', self.c_type)

    _c('}')

    _h('')
    _h('/**')
    _h(' * Return the iterator pointing to the last element')
    _h(' * @param i An %s', self.c_iterator_type)
    _h(' * @return  The iterator pointing to the last element')
    _h(' *')
    _h(' * Set the current element in the iterator to the last element.')
    _h(' * The member rem is set to 0. The member data points to the')
    _h(' * last element.')
    _h(' */')
    _c('')
    _hc('')
    _hc('/*****************************************************************************')
    _hc(' **')
    _hc(' ** xcb_generic_iterator_t %s', self.c_end_name)
    _hc(' ** ')
    _hc(' ** @param %s i', self.c_iterator_type)
    _hc(' ** @returns xcb_generic_iterator_t')
    _hc(' **')
    _hc(' *****************************************************************************/')
    _hc(' ')
    _hc('xcb_generic_iterator_t')
    _h('%s (%s i  /**< */);', self.c_end_name, self.c_iterator_type)
    _c('%s (%s i  /**< */)', self.c_end_name, self.c_iterator_type)
    _c('{')
    _c('    xcb_generic_iterator_t ret;')

    if self.fixed_size():
        _c('    ret.data = i.data + i.rem;')
        _c('    ret.index = i.index + ((char *) ret.data - (char *) i.data);')
        _c('    ret.rem = 0;')
    else:
        _c('    while(i.rem > 0)')
        _c('        %s(&i);', self.c_next_name)
        _c('    ret.data = i.data;')
        _c('    ret.rem = i.rem;')
        _c('    ret.index = i.index;')

    _c('    return ret;')
    _c('}')

def _c_accessor_get_length(expr, prefix=''):
    '''
    Figures out what C code is needed to get a length field.
    For fields that follow a variable-length field, use the accessor.
    Otherwise, just reference the structure field directly.
    '''
    prefarrow = '' if prefix == '' else prefix + '->'

    if expr.lenfield != None and expr.lenfield.prev_varsized_field != None:
        return expr.lenfield.c_accessor_name + '(' + prefix + ')'
    elif expr.lenfield_name != None:
        return prefarrow + expr.lenfield_name
    else:
        return str(expr.nmemb)

def _c_accessor_get_expr(expr, prefix=''):
    '''
    Figures out what C code is needed to get the length of a list field.
    Recurses for math operations.
    Returns bitcount for value-mask fields.
    Otherwise, uses the value of the length field.
    '''
    lenexp = _c_accessor_get_length(expr, prefix)

    if expr.op == '~':
        return '(' + '~' + _c_accessor_get_expr(expr.rhs, prefix) + ')'
    elif expr.op == 'popcount':
        return 'xcb_popcount(' + _c_accessor_get_expr(expr.rhs, prefix) + ')'
    elif expr.op == 'enumref':
        enum_name = expr.lenfield_type.name
        constant_name = expr.lenfield_name
        c_name = _n(enum_name + (constant_name,)).upper()
        return c_name
    elif expr.op == 'sumof':
        # 1. locate the referenced list object
        list_obj = expr.lenfield_type
        field = None
        for f in expr.lenfield_parent.fields:
            if f.field_name == expr.lenfield_name:
                field = f
                break
        if field is None:
            raise Exception("list field '%s' referenced by sumof not found" % expr.lenfield_name)
        if prefix != '':
            prefix = "%s->" % prefix
        list_name = "%s%s" % (prefix, field.c_field_name)
        c_length_func = "%s(%s%s)" % (field.c_length_name, prefix, field.c_field_name)
        return 'xcb_sumof(%s, %s)' % (list_name, c_length_func)
    elif expr.op != None:
        return '(' + _c_accessor_get_expr(expr.lhs, prefix) + ' ' + expr.op + ' ' + _c_accessor_get_expr(expr.rhs, prefix) + ')'
    elif expr.bitfield:
        return 'xcb_popcount(' + lenexp + ')'
    else:
        return lenexp

def _c_accessors_field(self, field):
    '''
    Declares the accessor functions for a non-list field that follows a variable-length field.
    '''
    if field.type.is_simple:
        _hc('')
        _hc('')
        _hc('/*****************************************************************************')
        _hc(' **')
        _hc(' ** %s %s', field.c_field_type, field.c_accessor_name)
        _hc(' ** ')
        _hc(' ** @param const %s *R', self.c_type)
        _hc(' ** @returns %s', field.c_field_type)
        _hc(' **')
        _hc(' *****************************************************************************/')
        _hc(' ')
        _hc('%s', field.c_field_type)
        _h('%s (const %s *R  /**< */);', field.c_accessor_name, self.c_type)
        _c('%s (const %s *R  /**< */)', field.c_accessor_name, self.c_type)
        _c('{')
        _c('    xcb_generic_iterator_t prev = %s;', _c_iterator_get_end(field.prev_varsized_field, 'R'))
        _c('    return * (%s *) ((char *) prev.data + XCB_TYPE_PAD(%s, prev.index) + %d);', 
           field.c_field_type, field.first_field_after_varsized.type.c_type, field.prev_varsized_offset)
        _c('}')
    else:
        _hc('')
        _hc('')
        _hc('/*****************************************************************************')
        _hc(' **')
        _hc(' ** %s * %s', field.c_field_type, field.c_accessor_name)
        _hc(' ** ')
        _hc(' ** @param const %s *R', self.c_type)
        _hc(' ** @returns %s *', field.c_field_type)
        _hc(' **')
        _hc(' *****************************************************************************/')
        _hc(' ')
        _hc('%s *', field.c_field_type)
        _h('%s (const %s *R  /**< */);', field.c_accessor_name, self.c_type)
        _c('%s (const %s *R  /**< */)', field.c_accessor_name, self.c_type)
        _c('{')
        _c('    xcb_generic_iterator_t prev = %s;', _c_iterator_get_end(field.prev_varsized_field, 'R'))
        _c('    return (%s *) ((char *) prev.data + XCB_TYPE_PAD(%s, prev.index) + %d);', field.c_field_type, field.first_field_after_varsized.type.c_type, field.prev_varsized_offset)
        _c('}')
    
def _c_accessors_list(self, field):
    '''
    Declares the accessor functions for a list field.
    Declares a direct-accessor function only if the list members are fixed size.
    Declares length and get-iterator functions always.
    '''
    list = field.type

    _h_setlevel(1)
    _c_setlevel(1)
    if list.member.fixed_size():
        _hc('')
        _hc('')
        _hc('/*****************************************************************************')
        _hc(' **')
        _hc(' ** %s * %s', field.c_field_type, field.c_accessor_name)
        _hc(' ** ')
        _hc(' ** @param const %s *R', self.c_type)
        _hc(' ** @returns %s *', field.c_field_type)
        _hc(' **')
        _hc(' *****************************************************************************/')
        _hc(' ')
        _hc('%s *', field.c_field_type)
        _h('%s (const %s *R  /**< */);', field.c_accessor_name, self.c_type)
        _c('%s (const %s *R  /**< */)', field.c_accessor_name, self.c_type)
        _c('{')

        if field.prev_varsized_field == None:
            _c('    return (%s *) (R + 1);', field.c_field_type)
        else:
            _c('    xcb_generic_iterator_t prev = %s;', _c_iterator_get_end(field.prev_varsized_field, 'R'))
            _c('    return (%s *) ((char *) prev.data + XCB_TYPE_PAD(%s, prev.index) + %d);', field.c_field_type, field.first_field_after_varsized.type.c_type, field.prev_varsized_offset)

        _c('}')

    _hc('')
    _hc('')
    _hc('/*****************************************************************************')
    _hc(' **')
    _hc(' ** int %s', field.c_length_name)
    _hc(' ** ')
    _hc(' ** @param const %s *R', self.c_type)
    _hc(' ** @returns int')
    _hc(' **')
    _hc(' *****************************************************************************/')
    _hc(' ')
    _hc('int')
    _h('%s (const %s *R  /**< */);', field.c_length_name, self.c_type)
    _c('%s (const %s *R  /**< */)', field.c_length_name, self.c_type)
    _c('{')
    _c('    return %s;', _c_accessor_get_expr(field.type.expr, 'R'))
    _c('}')

    if field.type.member.is_simple:
        _hc('')
        _hc('')
        _hc('/*****************************************************************************')
        _hc(' **')
        _hc(' ** xcb_generic_iterator_t %s', field.c_end_name)
        _hc(' ** ')
        _hc(' ** @param const %s *R', self.c_type)
        _hc(' ** @returns xcb_generic_iterator_t')
        _hc(' **')
        _hc(' *****************************************************************************/')
        _hc(' ')
        _hc('xcb_generic_iterator_t')
        _h('%s (const %s *R  /**< */);', field.c_end_name, self.c_type)
        _c('%s (const %s *R  /**< */)', field.c_end_name, self.c_type)
        _c('{')
        _c('    xcb_generic_iterator_t i;')

        if field.prev_varsized_field == None:
            _c('    i.data = ((%s *) (R + 1)) + (%s);', field.type.c_wiretype, _c_accessor_get_expr(field.type.expr, 'R'))
        else:
            _c('    xcb_generic_iterator_t child = %s;', _c_iterator_get_end(field.prev_varsized_field, 'R'))
            _c('    i.data = ((%s *) child.data) + (%s);', field.type.c_wiretype, _c_accessor_get_expr(field.type.expr, 'R'))

        _c('    i.rem = 0;')
        _c('    i.index = (char *) i.data - (char *) R;')
        _c('    return i;')
        _c('}')

    else:
        _hc('')
        _hc('')
        _hc('/*****************************************************************************')
        _hc(' **')
        _hc(' ** %s %s', field.c_iterator_type, field.c_iterator_name)
        _hc(' ** ')
        _hc(' ** @param const %s *R', self.c_type)
        _hc(' ** @returns %s', field.c_iterator_type)
        _hc(' **')
        _hc(' *****************************************************************************/')
        _hc(' ')
        _hc('%s', field.c_iterator_type)
        _h('%s (const %s *R  /**< */);', field.c_iterator_name, self.c_type)
        _c('%s (const %s *R  /**< */)', field.c_iterator_name, self.c_type)
        _c('{')
        _c('    %s i;', field.c_iterator_type)

        if field.prev_varsized_field == None:
            _c('    i.data = (%s *) (R + 1);', field.c_field_type)
        else:
            _c('    xcb_generic_iterator_t prev = %s;', _c_iterator_get_end(field.prev_varsized_field, 'R'))
            _c('    i.data = (%s *) ((char *) prev.data + XCB_TYPE_PAD(%s, prev.index));', field.c_field_type, field.c_field_type)

        _c('    i.rem = %s;', _c_accessor_get_expr(field.type.expr, 'R'))
        _c('    i.index = (char *) i.data - (char *) R;')
        _c('    return i;')
        _c('}')

def _c_accessors(self, name, base):
    '''
    Declares the accessor functions for the fields of a structure.
    '''
    for field in self.fields:
        if field.type.is_list and not field.type.fixed_size():
            _c_accessors_list(self, field)
        elif field.prev_varsized_field != None:
            _c_accessors_field(self, field)

def c_simple(self, name):
    '''
    Exported function that handles cardinal type declarations.
    These are types which are typedef'd to one of the CARDx's, char, float, etc.
    '''
    _c_type_setup(self, name, ())

    if (self.name != name):
        # Typedef
        _h_setlevel(0)
        my_name = _t(name)
        _h('')
        _h('typedef %s %s;', _t(self.name), my_name)

        # Iterator
        _c_iterator(self, name)

def _c_complex(self):
    '''
    Helper function for handling all structure types.
    Called for all structs, requests, replies, events, errors.
    '''
    _h_setlevel(0)
    _h('')
    _h('/**')
    _h(' * @brief %s', self.c_type)
    _h(' **/')
    _h('typedef %s %s {', self.c_container, self.c_type)

    struct_fields = []
    maxtypelen = 0

    varfield = None
    for field in self.fields:
        if not field.type.fixed_size() and not self.is_switch:
            varfield = field.c_field_name
            continue
        if varfield != None and not field.type.is_pad and field.wire:
            errmsg = '%s: warning: variable field %s followed by fixed field %s\n' % (self.c_type, varfield, field.c_field_name)
            sys.stderr.write(errmsg)
            # sys.exit(1)
        if field.wire:
            struct_fields.append(field)
        
    for field in struct_fields:
        length = len(field.c_field_type)
        # account for '*' pointer_spec
        if not field.type.fixed_size():
            length += 1
        maxtypelen = max(maxtypelen, length)

    for field in struct_fields:
        if (field.type.fixed_size() or 
            # in case of switch with switch children, don't make the field a pointer
            # necessary for unserialize to work
            (self.is_switch and field.type.is_switch)):
            spacing = ' ' * (maxtypelen - len(field.c_field_type))
            _h('    %s%s %s%s; /**<  */', field.c_field_type, spacing, field.c_field_name, field.c_subscript)
        
        else:
            spacing = ' ' * (maxtypelen - (len(field.c_field_type) + 1))
            _h('    %s%s *%s%s; /**<  */', field.c_field_type, spacing, field.c_field_name, field.c_subscript)

    _h('} %s;', self.c_type)

def c_struct(self, name):
    '''
    Exported function that handles structure declarations.
    '''
    _c_type_setup(self, name, ())
    _c_complex(self)
    _c_accessors(self, name, name)
    _c_iterator(self, name)

def c_union(self, name):
    '''
    Exported function that handles union declarations.
    '''
    _c_type_setup(self, name, ())
    _c_complex(self)
    _c_iterator(self, name)

def _c_request_helper(self, name, cookie_type, void, regular, aux=False):
    '''
    Declares a request function.
    '''

    # Four stunningly confusing possibilities here:
    #
    #   Void            Non-void
    # ------------------------------
    # "req"            "req"
    # 0 flag           CHECKED flag   Normal Mode
    # void_cookie      req_cookie
    # ------------------------------
    # "req_checked"    "req_unchecked"
    # CHECKED flag     0 flag         Abnormal Mode
    # void_cookie      req_cookie
    # ------------------------------


    # Whether we are _checked or _unchecked
    checked = void and not regular
    unchecked = not void and not regular

    # What kind of cookie we return
    func_cookie = 'xcb_void_cookie_t' if void else self.c_cookie_type

    # What flag is passed to xcb_request
    func_flags = '0' if (void and regular) or (not void and not regular) else 'XCB_REQUEST_CHECKED'

    # Global extension id variable or NULL for xproto
    func_ext_global = '&' + _ns.c_ext_global_name if _ns.is_ext else '0'

    # What our function name is
    func_name = self.c_request_name if not aux else self.c_aux_name
    if checked:
        func_name = self.c_checked_name if not aux else self.c_aux_checked_name
    if unchecked:
        func_name = self.c_unchecked_name if not aux else self.c_aux_unchecked_name

    param_fields = []
    wire_fields = []
    maxtypelen = len('xcb_connection_t')
    serial_fields = []

    for field in self.fields:
        if field.visible:
            # The field should appear as a call parameter
            param_fields.append(field)
        if field.wire and not field.auto:
            # We need to set the field up in the structure
            wire_fields.append(field)
        if field.type.need_serialize:
            serial_fields.append(field)
        
    for field in param_fields:
        c_field_const_type = field.c_field_const_type 
        if field.type.need_serialize and not aux:
            c_field_const_type = "const void"
        if len(c_field_const_type) > maxtypelen:
            maxtypelen = len(c_field_const_type)

    _h_setlevel(1)
    _c_setlevel(1)
    _h('')
    _h('/**')
    _h(' * Delivers a request to the X server')
    _h(' * @param c The connection')
    _h(' * @return A cookie')
    _h(' *')
    _h(' * Delivers a request to the X server.')
    _h(' * ')
    if checked:
        _h(' * This form can be used only if the request will not cause')
        _h(' * a reply to be generated. Any returned error will be')
        _h(' * saved for handling by xcb_request_check().')
    if unchecked:
        _h(' * This form can be used only if the request will cause')
        _h(' * a reply to be generated. Any returned error will be')
        _h(' * placed in the event queue.')
    _h(' */')
    _c('')
    _hc('')
    _hc('/*****************************************************************************')
    _hc(' **')
    _hc(' ** %s %s', cookie_type, func_name)
    _hc(' ** ')

    spacing = ' ' * (maxtypelen - len('xcb_connection_t'))
    _hc(' ** @param xcb_connection_t%s *c', spacing)

    for field in param_fields:
        c_field_const_type = field.c_field_const_type 
        if field.type.need_serialize and not aux:
            c_field_const_type = "const void"
        spacing = ' ' * (maxtypelen - len(c_field_const_type))
        _hc(' ** @param %s%s %s%s', c_field_const_type, spacing, field.c_pointer, field.c_field_name)

    _hc(' ** @returns %s', cookie_type)
    _hc(' **')
    _hc(' *****************************************************************************/')
    _hc(' ')
    _hc('%s', cookie_type)

    spacing = ' ' * (maxtypelen - len('xcb_connection_t'))
    comma = ',' if len(param_fields) else ');'
    _h('%s (xcb_connection_t%s *c  /**< */%s', func_name, spacing, comma)
    comma = ',' if len(param_fields) else ')'
    _c('%s (xcb_connection_t%s *c  /**< */%s', func_name, spacing, comma)

    func_spacing = ' ' * (len(func_name) + 2)
    count = len(param_fields)
    for field in param_fields:
        count = count - 1
        c_field_const_type = field.c_field_const_type 
        if field.type.need_serialize and not aux:
            c_field_const_type = "const void"
        spacing = ' ' * (maxtypelen - len(c_field_const_type))
        comma = ',' if count else ');'
        _h('%s%s%s %s%s  /**< */%s', func_spacing, c_field_const_type, 
           spacing, field.c_pointer, field.c_field_name, comma)
        comma = ',' if count else ')'
        _c('%s%s%s %s%s  /**< */%s', func_spacing, c_field_const_type, 
           spacing, field.c_pointer, field.c_field_name, comma)

    count = 2
    for field in param_fields:
        if not field.type.fixed_size():
            count = count + 2
            if field.type.need_serialize:
                # _serialize() keeps track of padding automatically
                count -= 1

    _c('{')
    _c('    static const xcb_protocol_request_t xcb_req = {')
    _c('        /* count */ %d,', count)
    _c('        /* ext */ %s,', func_ext_global)
    _c('        /* opcode */ %s,', self.c_request_name.upper())
    _c('        /* isvoid */ %d', 1 if void else 0)
    _c('    };')
    _c('    ')

    _c('    struct iovec xcb_parts[%d];', count + 2)
    _c('    %s xcb_ret;', func_cookie)
    _c('    %s xcb_out;', self.c_type)
    for idx, f in enumerate(serial_fields):
        if not aux:
            _c('    %s xcb_aux%d;' % (f.type.c_type, idx))
        else:
            _c('    void *xcb_aux%d = 0;' % (idx))
    _c('    ')
    _c('    printf("in function %s\\n");' % func_name)     
 
    # fixed size fields
    for field in wire_fields:
        if field.type.fixed_size():
            if field.type.is_expr:
                _c('    xcb_out.%s = %s;', field.c_field_name, _c_accessor_get_expr(field.type.expr))
            elif field.type.is_pad:
                if field.type.nmemb == 1:
                    _c('    xcb_out.%s = 0;', field.c_field_name)
                else:
                    _c('    memset(xcb_out.%s, 0, %d);', field.c_field_name, field.type.nmemb)
            else:
                if field.type.nmemb == 1:
                    _c('    xcb_out.%s = %s;', field.c_field_name, field.c_field_name)
                else:
                    _c('    memcpy(xcb_out.%s, %s, %d);', field.c_field_name, field.c_field_name, field.type.nmemb)

    _c('    ')
    _c('    xcb_parts[2].iov_base = (char *) &xcb_out;')
    _c('    xcb_parts[2].iov_len = sizeof(xcb_out);')
    _c('    xcb_parts[3].iov_base = 0;')
    _c('    xcb_parts[3].iov_len = -xcb_parts[2].iov_len & 3;')

    # calls in order to free dyn. all. memory
    free_calls = []
    count = 4
    for field in param_fields:
        if not field.type.fixed_size():
            if not field.type.need_serialize:
                _c('    xcb_parts[%d].iov_base = (char *) %s;', count, field.c_field_name)
            else:
                if not aux:
                    _c('    xcb_parts[%d].iov_base = (char *) %s;', count, field.c_field_name)
                idx = serial_fields.index(field)
                if not aux:
                    serialize_args = get_serialize_params('unserialize', field.type, 
                                                          field.c_field_name, 
                                                          '&xcb_aux%d' % idx)[2]
                else:
                    serialize_args = get_serialize_params('serialize', field.type, 
                                                          '&xcb_aux%d' % idx,
                                                          field.c_field_name)[2]
                serialize_args = reduce(lambda x,y: "%s, %s" % (x,y), [a[2] for a in serialize_args])
                _c('    xcb_parts[%d].iov_len = ', count)
                if aux:
                    _c('      %s (%s);', field.type.c_serialize_name, serialize_args)
                    _c('    xcb_parts[%d].iov_base = xcb_aux%d;' % (count, idx))
                    free_calls.append('    free(xcb_aux%d);' % idx)
                else:
                    _c('      %s (%s);', field.type.c_unserialize_name, serialize_args)
            if field.type.is_list:
                _c('    xcb_parts[%d].iov_len = %s * sizeof(%s);', count, 
                   _c_accessor_get_expr(field.type.expr), field.type.member.c_wiretype)
            elif not field.type.need_serialize:
                # FIXME - _serialize()
                _c('    xcb_parts[%d].iov_len = %s * sizeof(%s);', 
                   count, 'Uh oh', field.type.c_wiretype)
            
            count += 1
            if not field.type.need_serialize:
                # the _serialize() function keeps track of padding automatically
                _c('    xcb_parts[%d].iov_base = 0;', count)
                _c('    xcb_parts[%d].iov_len = -xcb_parts[%d].iov_len & 3;', count, count-1)
                count += 1

    _c('    ')
    _c('    xcb_ret.sequence = xcb_send_request(c, %s, xcb_parts + 2, &xcb_req);', func_flags)
    
    # free dyn. all. data, if any
    for f in free_calls:
        _c(f)
    _c('    return xcb_ret;')
    _c('}')

def _c_reply(self, name):
    '''
    Declares the function that returns the reply structure.
    '''
    spacing1 = ' ' * (len(self.c_cookie_type) - len('xcb_connection_t'))
    spacing2 = ' ' * (len(self.c_cookie_type) - len('xcb_generic_error_t'))
    spacing3 = ' ' * (len(self.c_reply_name) + 2)

    _h('')
    _h('/**')
    _h(' * Return the reply')
    _h(' * @param c      The connection')
    _h(' * @param cookie The cookie')
    _h(' * @param e      The xcb_generic_error_t supplied')
    _h(' *')
    _h(' * Returns the reply of the request asked by')
    _h(' * ')
    _h(' * The parameter @p e supplied to this function must be NULL if')
    _h(' * %s(). is used.', self.c_unchecked_name)
    _h(' * Otherwise, it stores the error if any.')
    _h(' *')
    _h(' * The returned value must be freed by the caller using free().')
    _h(' */')
    _c('')
    _hc('')
    _hc('/*****************************************************************************')
    _hc(' **')
    _hc(' ** %s * %s', self.c_reply_type, self.c_reply_name)
    _hc(' ** ')
    _hc(' ** @param xcb_connection_t%s  *c', spacing1)
    _hc(' ** @param %s   cookie', self.c_cookie_type)
    _hc(' ** @param xcb_generic_error_t%s **e', spacing2)
    _hc(' ** @returns %s *', self.c_reply_type)
    _hc(' **')
    _hc(' *****************************************************************************/')
    _hc(' ')
    _hc('%s *', self.c_reply_type)
    _hc('%s (xcb_connection_t%s  *c  /**< */,', self.c_reply_name, spacing1)
    _hc('%s%s   cookie  /**< */,', spacing3, self.c_cookie_type)
    _h('%sxcb_generic_error_t%s **e  /**< */);', spacing3, spacing2)
    _c('%sxcb_generic_error_t%s **e  /**< */)', spacing3, spacing2)
    _c('{')
    _c('    return (%s *) xcb_wait_for_reply(c, cookie.sequence, e);', self.c_reply_type)
    _c('}')

def _c_opcode(name, opcode):
    '''
    Declares the opcode define for requests, events, and errors.
    '''
    _h_setlevel(0)
    _h('')
    _h('/** Opcode for %s. */', _n(name))
    _h('#define %s %s', _n(name).upper(), opcode)
    
def _c_cookie(self, name):
    '''
    Declares the cookie type for a non-void request.
    '''
    _h_setlevel(0)
    _h('')
    _h('/**')
    _h(' * @brief %s', self.c_cookie_type)
    _h(' **/')
    _h('typedef struct %s {', self.c_cookie_type)
    _h('    unsigned int sequence; /**<  */')
    _h('} %s;', self.c_cookie_type)

def c_request(self, name):
    '''
    Exported function that handles request declarations.
    '''
    _c_type_setup(self, name, ('request',))

    if self.reply:
        # Cookie type declaration
        _c_cookie(self, name)

    # Opcode define
    _c_opcode(name, self.opcode)

    # Request structure declaration
    _c_complex(self)

    if self.reply:
        _c_type_setup(self.reply, name, ('reply',))
        # Reply structure definition
        _c_complex(self.reply)
        # Request prototypes
        _c_request_helper(self, name, self.c_cookie_type, False, True)
        _c_request_helper(self, name, self.c_cookie_type, False, False)
        if self.need_aux:
            _c_request_helper(self, name, self.c_cookie_type, False, True, True)
            _c_request_helper(self, name, self.c_cookie_type, False, False, True)
        # Reply accessors
        _c_accessors(self.reply, name + ('reply',), name)
        _c_reply(self, name)
    else:
        # Request prototypes
        _c_request_helper(self, name, 'xcb_void_cookie_t', True, False)
        _c_request_helper(self, name, 'xcb_void_cookie_t', True, True)
        if self.need_aux:
            _c_request_helper(self, name, 'xcb_void_cookie_t', True, False, True)
            _c_request_helper(self, name, 'xcb_void_cookie_t', True, True, True)


def c_event(self, name):
    '''
    Exported function that handles event declarations.
    '''
    _c_type_setup(self, name, ('event',))

    # Opcode define
    _c_opcode(name, self.opcodes[name])

    if self.name == name:
        # Structure definition
        _c_complex(self)
    else:
        # Typedef
        _h('')
        _h('typedef %s %s;', _t(self.name + ('event',)), _t(name + ('event',)))

def c_error(self, name):
    '''
    Exported function that handles error declarations.
    '''
    _c_type_setup(self, name, ('error',))

    # Opcode define
    _c_opcode(name, self.opcodes[name])

    if self.name == name:
        # Structure definition
        _c_complex(self)
    else:
        # Typedef
        _h('')
        _h('typedef %s %s;', _t(self.name + ('error',)), _t(name + ('error',)))


# Main routine starts here

# Must create an "output" dictionary before any xcbgen imports.
output = {'open'    : c_open,
          'close'   : c_close,
          'simple'  : c_simple,
          'enum'    : c_enum,
          'struct'  : c_struct,
          'union'   : c_union,
          'request' : c_request,
          'event'   : c_event,
          'error'   : c_error, 
          }

# Boilerplate below this point

# Check for the argument that specifies path to the xcbgen python package.
try:
    opts, args = getopt.getopt(sys.argv[1:], 'p:')
except getopt.GetoptError, err:
    print str(err)
    print 'Usage: c_client.py [-p path] file.xml'
    sys.exit(1)

for (opt, arg) in opts:
    if opt == '-p':
        sys.path.append(arg)

# Import the module class
try:
    from xcbgen.state import Module
except ImportError:
    print ''
    print 'Failed to load the xcbgen Python package!'
    print 'Make sure that xcb/proto installed it on your Python path.'
    print 'If not, you will need to create a .pth file or define $PYTHONPATH'
    print 'to extend the path.'
    print 'Refer to the README file in xcb/proto for more info.'
    print ''
    raise

# Parse the xml header
module = Module(args[0], output)

# Build type-registry and resolve type dependencies
module.register()
module.resolve()

# Output the code
module.generate()
