"""Read-only SPI NOR image model for mode 0, MSB-first eight-bit transfers.

Supports READ (03), FAST_READ (0b, one dummy byte), status (05), and an
explicit project-supplied JEDEC identity (9f). Programming/erase are refused.
"""
from collections import Counter
from dataclasses import replace
from .apb import ProtocolError, NoChecks
from .spi import Pins


class ReadOnlyNor:
    def __init__(self, image=b'', *, capacity=65536, jedec=None):
        if not isinstance(image,bytes) or type(capacity) is not int or capacity<len(image) or capacity<1:
            raise ValueError('flash needs bytes and a positive capacity covering the image')
        if jedec is not None and (not isinstance(jedec,bytes) or len(jedec)!=3):
            raise ValueError('JEDEC identity must be three project-supplied bytes')
        self.image=image+bytes([255])*(capacity-len(image))
        self.jedec=jedec
        self.coverage=Counter()
        self.previous=Pins()
        self.miso=1
        self._select()

    def _select(self):
        self.state='command';self.command=None;self.address=0;self.address_bytes=0
        self.bit=0;self.received=0;self.outgoing=255;self.id_index=0

    def _read(self):
        return self.image[self.address] if self.address<len(self.image) else 255

    def _byte(self, value):
        self.coverage['words']+=1
        if self.state=='command':
            if value not in (3,11,5,159):
                raise ProtocolError(f'SPI_FLASH_UNSUPPORTED_COMMAND:{value:02x}')
            self.command=value;self.coverage[('command',value)]+=1
            if value in (3,11):self.state='address';return 255
            if value==5:self.state='status';return 0
            if self.jedec is None:raise ProtocolError('SPI_FLASH_JEDEC_INPUT_REQUIRED')
            self.state='identity';return self.jedec[0]
        if self.state=='address':
            self.address=(self.address<<8)|value;self.address_bytes+=1
            if self.address_bytes==3:
                self.state='dummy' if self.command==11 else 'read'
                return 255 if self.state=='dummy' else self._read()
            return 255
        if self.state=='dummy':self.state='read';return self._read()
        if self.state=='read':
            self.coverage['read_bytes']+=1
            self.address=(self.address+1)&0xffffff
            return self._read()
        if self.state=='identity':
            self.id_index+=1
            return self.jedec[self.id_index] if self.id_index<3 else 255
        return 0  # Read-only model has no write-in-progress or write-enable latch.

    def step(self,p):
        if any(value not in (0,1) for value in (p.reset_n,p.cs_n,p.sclk,p.mosi)):
            raise ProtocolError('SPI_UNKNOWN_PIN')
        old,self.previous=self.previous,p
        if not p.reset_n:
            self._select();self.miso=1
            return replace(p,miso=1)
        if p.cs_n:
            if not old.cs_n:
                if self.bit:raise ProtocolError('SPI_FLASH_PARTIAL_WORD')
                self.coverage['transactions']+=1
            self.miso=1
            return replace(p,miso=1)
        if old.cs_n:
            if p.sclk:raise ProtocolError('SPI_FLASH_MODE_ZERO_REQUIRED')
            self._select();self.miso=1
        if not old.sclk and p.sclk:
            self.received=(self.received<<1)|p.mosi
            self.bit+=1
            if self.bit==8:
                self.outgoing=self._byte(self.received)
                self.bit=0;self.received=0
        if old.sclk and not p.sclk:
            self.miso=(self.outgoing>>(7-self.bit))&1
        return replace(p,miso=self.miso)

    def finish(self):
        if not self.previous.cs_n or self.bit:
            raise ProtocolError('SPI_FLASH_UNFINISHED_TRANSACTION')
        if not self.coverage['read_bytes']:
            raise NoChecks('SPI_FLASH_NO_READS')
        return dict(read_bytes=self.coverage['read_bytes'],transactions=self.coverage['transactions'],
                    words=self.coverage['words'])
