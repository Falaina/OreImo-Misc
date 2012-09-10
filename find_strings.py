# -*- coding: utf-8 -*-
from __future__ import print_function
import unicodedata
from binascii import unhexlify, hexlify
import re
import sys
from struct import unpack
from array import array
printable = ['L', 'P', 'N', 'M', 'S', 'Z']

if len(sys.argv) < 3:
   print('Usage: find_strings.py input-file output-file')
   exit(-1)

f = open(sys.argv[1], 'rb')

txts = []
for j in range(4):
   f.seek(j)
   txt = f.read()
   print(len(txt)&(~0x3), 'txtlen')
   a = array('I', txt[:len(txt)&(~0x3)])

   txts.append(a)
strings = []
i= 0

ascii_re = re.compile('^[\x00-\x1F]')

def try_string(chars, encoding):
      try:
         s = chars.decode(encoding)
         num_printable = 0
         last_printable = 0
         num_unprintable = 0
         for s_idx, c in enumerate(s):
            if (unicodedata.category(c)[0] in printable and
                c not in u'㔀㐀䄀Ϩ'):
               num_printable += 1
               last_printable = s_idx
            else:
               num_unprintable += 1
         if num_printable >= 2 and num_unprintable <= 3 \
                and num_printable > num_unprintable \
                and (not ascii_re.match(s)):
            print('Seemingly valid string at %x' %(offset,) )
            return (offset, last_printable, chars.decode(encoding).encode('utf-8'))
      except Exception as e:
         if hasattr(e, 'message'):
            print(e.message)
      return None
      
   

for array_no, a in enumerate(txts):
   i=0
   while i < len(a):
      b = a[i]
      if b >= 0x2 and b < 0x70:
         encodings = [('utf-32-le', 4, 4),
                      # Assume no surrogates
                      ('utf-16-le', 2, 2), 
                      # Max bytes per code point is actually 6
                      #  for utf-8, but let's assume BMP
                      #('utf-8', 1, 3)] 
                      ]
         base = i
         candidates = []
         for (encoding, min_bpc, max_bpc) in encodings:
            if (b * max_bpc) < (2*min_bpc):
               continue
            i = base
            offset = i * 4 + array_no + 4
            print('Potential %s string %d chars, %x' % (encoding, b, offset))
            f.seek(offset)
            chars = f.read(b * max_bpc)
            info = try_string(chars, encoding)
            if info is not None:
               print('Found %s string %d chars' % (encoding, len(info[2].decode('utf-8'))))
               last_printable = info[1]
               if i + 1 < len(a):
                  next_len =a[i+1]
                  if next_len < b:
                     offset += 4
                     f.seek(offset)
                     chars_2 = f.read( next_len * 2)
                     info_2  = try_string(chars_2, encoding)
                     if info_2 is not None:
                        last_printable += 4
                        info = info_2
               if encoding != 'utf-16-le': # Be stricter on non-utf-16-le
                  if last_printable < b - 1:
                     continue
                  # Assume decomposables are wrong
                  invalid = False
                  for c in info[2].decode('utf-8'):
                     if unicodedata.decomposition(c) != '':
                        invalid = True
                     if unicodedata.category(c)[0] in ['C']:
                        invalid = True
                  if invalid:
                     continue
               print('Adding %s candiddate at %x' % (encoding, offset))
               candidates.append(info + ((encoding, min_bpc),))
         cur_choice = None
         for candidate in candidates:
            (s_offset, last_printable, charstring, _) = candidate
            print('Considering cnadidatestring at <%x> %d printable chars' % (s_offset, last_printable))
            if cur_choice is None:
               cur_choice = candidate
            if candidate[1] > cur_choice[1]:
               cur_choice = candidate
         if cur_choice:
            (s_offset, last_printable, charstring, (encoding, min_bpc)) = cur_choice
            size = len(charstring.decode('utf-8').encode(encoding))
            next_offset = (i * 4 + array_no + 4) + size
            i += (size/4) + 1
            strings.append((s_offset, next_offset, encoding, charstring))
            print('[%d - %d] Chose %s at <%x> - next offset %x' % (array_no, i, encoding, s_offset, next_offset))
         else:
            i += 1
      else:
         i += 1

from pprint import pprint
out = open(sys.argv[2], 'w+b')
out.write(unhexlify('efbbbf'))
#out.write('-*- coding: utf-8 -*-\r\n')
sorted_strings = sorted(strings, key=lambda s: s[0])
for i, (offset, end, encoding, s) in enumerate(sorted_strings):
   raw = ''
   if i + 1 < len(sorted_strings):
      next_offset = sorted_strings[i+1][0]
      if next_offset-end - 4 > 0:
         f.seek(end)
         raw =f.read(next_offset-end - 4)
   out.write('<%x>\r\n[%s] %s \r\n<%x>\r\n' % (offset, encoding, s.replace('\n', ''),end))
   if raw != '':
      out.write('After: %s\r\n' % (hexlify(raw),))
   out.write('\r\n')
out.close()
