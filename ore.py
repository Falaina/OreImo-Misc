#! -*- coding: utf-8 -*-
# Packer for the ORE section of envpsp.dat
from __future__ import print_function
import sys
sys.path[0:0] = ['libs', '.']

from mmap import mmap, ACCESS_COPY
from binascii import hexlify
from struct import unpack, pack, Struct
from cStringIO import StringIO
from pypgf.pypgf import PGFFont

INFO_OFFSET = 0xac62
DEBUG_MODE  = True
uint_le = Struct('<I')

_print = print
def print(*args, **kwargs):
   if 'debug' not in kwargs:
      kwargs['debug'] = False
   debug = kwargs['debug']
   if (not debug) or (debug and DEBUG_MODE):
      _print(*args)

def chunked_copy(buf1, buf2, cnt, chunk_size=2**28):
   cur_cnt = 0
   while cur_cnt < cnt:
      to_read = min(cnt - cur_cnt,  chunk_size)
      buf2.write(buf1.read(to_read))
      cur_cnt += to_read
   print('Read %d bytes' %( cur_cnt))

class Buffer(object):
   def __init__(self, buf):
      self.buf = buf

   def allocate_at(self, idx, new_bytes):
      buf = self.buf
      size = buf.size()
      new_buf = mmap(-1, new_bytes + size) 
      self.buf.seek(0)
      chunked_copy(buf, new_buf, idx)
      new_buf.seek(idx + new_bytes)
      chunked_copy(buf, new_buf, size-idx)
      self.buf.close()
      self.buf = new_buf

   def save(self, filepath):
      with open(filepath, 'w+b') as f:
         buf = self.buf
         buf.seek(0)
         f.write(buf.read(-1))
         f.flush()

def UInt(buf, offset=None):
   class UInt(int): 
      def pack(self):
         return pack('<I', self)

   if offset is not None:
      buf.seek(offset)
   if hasattr(buf, 'read'):
      return UInt(uint_le.unpack(buf.read(4))[0])
   else:
      return UInt(buf)

class LString(object):
   """ Length-prefixed String """

   __slots__ = ['len', 'raw', 'codec']
   def __init__(self, buf, offset=None, codec='utf-16-le'):
      if offset is not None:
         buf.seek(offset)
      self.len = str_len = UInt(buf)
      self.codec = codec
      self.raw = buf.read(self.len * 2)

   def pack(self):
      return uint_le.pack(self.len) +  self.raw
      
   @property
   def decoded(self):
      return self.raw.decode(self.codec)

   def __repr__(self):
      return self.raw

   def __str__(self):
      return self.decoded

   @staticmethod
   def from_str(str):
      l = UInt(len(str))
      return LString(StringIO(l.pack() + str.encode('utf-16-le')))

class PackableList(list):
   def __init__(self, *args):
      super(PackableList, self).__init__(*args)

   def pack(self):
      out = ''
      for elem in self:
         out += elem.pack()
      return out

class OrnamentString(object):
   def __init__(self, s):
      self.lines = s.split('_')
      
class OrnamentEntry(object):
   def __init__(self, buf, offset=None):
      if offset is not None:
         buf.seek(offset)
      self.title = LString(buf)
      print('[Parsing] Title: %s' % (self.title), debug=True)
      self.num_pages = UInt(buf)
      print('[Parsing] NumPages: [%x] %d' % (buf.tell(), self.num_pages), debug=True)
      self.pages = PackableList()
      for _ in range(self.num_pages):
         self.pages.append(LString(buf))
      for page in self.pages:
         print(page.decoded.encode('utf-8'), debug=True)
      
   def pack(self):
      return self.title.pack() + self.num_pages.pack() + self.pages.pack()

   def replace(self, pgf, txt, w, h):
      chunks = pgf.wrap_text(txt, w, h)
      self.num_pages = UInt((len(chunks) / 7) + 1)
      self.pages = PackableList()
      for i in range(self.num_pages):
         lines = chunks[i*7:(i+1)*7]
         self.pages.append(LString.from_str('_'.join(lines)))

class OrnamentInfo(object):
   def __init__(self, buf, offset=INFO_OFFSET):
      self.title = LString(buf, offset)
      assert self.title.decoded == u'ORNAMENT INFORMATION'
      self._info = unpack('<IIfIII', buf.read(0x18))
      self.info = PackableList([UInt(x) for x in self._info])
      self.num_entries = self.info[5]
      self.entries = PackableList()
      for _ in range(self.num_entries):
         self.entries.append(OrnamentEntry(buf))

   def pack(self):
      return self.title.pack() + self.info.pack() + self.entries.pack()

def parse_ornament():
   f = open('envpsp.dat', 'rb')
   b = Buffer(mmap(f.fileno(), 0, access=ACCESS_COPY))
   oi = OrnamentInfo(f)

def pack_test():
   global DEBUG_MODE
   f = open('envpsp.dat', 'rb')
   b = Buffer(mmap(f.fileno(), 0, access=ACCESS_COPY))
   oi = OrnamentInfo(f)

   l = 'A Siscaly knockout tournament has been organized nationwide in order to choose the strongest "Sister User". To Kirino, who really loves sister-related games, she has alot of interest in this tournament. On a side note, Siscalys official title is [Shin Imouto Taisen Siscalypse], a 3D Bishoujo versus game. And so, I probably cant refuse to participate...'

   pgf = PGFFont('../pypgf/fonts/sonyjpn.pgf')
   w = 360 * 64
   h = (pgf.maxSizeV/64 * 3) + pgf.maxGlyphH + 10
   old_size = len(oi.pack())
   oi.entries[0].replace(pgf, l, w, h)
   print([page.decoded for page in oi.entries[0].pages], debug=True)
   new_oi = StringIO(oi.pack())
   print(hexlify(oi.entries[0].pack()), debug=True)
   DEBUG_MODE = False
   new_oi = OrnamentInfo(new_oi, 0)
   new_size = len(new_oi.pack())
   print(new_oi.entries[0].pages, debug=True)
   DEBUG_MODE = True
   print('Need %d bytes' % (new_size - old_size))
   b.allocate_at(INFO_OFFSET, new_size - old_size)
   b.buf.seek(INFO_OFFSET)
   b.buf.write(new_oi.pack())
   b.save('envpsp.dat')
   f.close()


if __name__ == '__main__':
   pack_test()

