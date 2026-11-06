/* USB serial for Chrome (WebUSB). Talks to an Arduino over USB-OTG with no app install.
   Drivers: CH340/CH341 (most clone Unos) and CDC-ACM (genuine Uno R3 with the 16U2 chip).
   Based on the open-source usb-serial-for-android CH34x sequence; tested here with a mock device only. */
const UsbSerial = (() => {
  const VENDORS = [0x1a86, 0x2341, 0x2a03];            // CH340, Arduino, Arduino.org
  const FILTERS = VENDORS.map(v => ({ vendorId: v }));
  const CH340_BAUD = { 2400: [0xd901, 0x0038], 4800: [0x6402, 0x001f], 9600: [0xb202, 0x0013], 19200: [0xd902, 0x000d], 38400: [0x6403, 0x000a], 115200: [0xcc03, 0x0008] };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const supported = () => typeof navigator !== 'undefined' && !!navigator.usb;
  const hex = n => '0x' + n.toString(16).padStart(4, '0');
  const enc = t => (typeof t === 'string' ? new TextEncoder().encode(t) : t);

  async function claimIface(dev, n, log) {
    try { await dev.claimInterface(n); return; } catch (e) {
      log('claim failed (' + e.message + '). Resetting the device and trying once more');
      try { await dev.reset(); } catch (e2) { log('reset not possible: ' + e2.message); }
      try { await dev.close(); } catch (e3) {}
      await dev.open(); if (dev.configuration === null) await dev.selectConfiguration(1);
      try { await dev.claimInterface(n); } catch (e4) {
        throw new Error('Another app or Chrome tab is already using the Arduino. Close the serial app (swipe it away in recent apps) and any other AgriSahayak tab, unplug and plug in the Arduino, then press Connect. [' + e4.message + ']');
      }
    }
  }

  async function endpoints(dev, ifaceNumbers) {
    for (const i of dev.configuration.interfaces) {
      if (!ifaceNumbers.includes(i.interfaceNumber)) continue;
      const eps = i.alternates[0].endpoints;
      const inEp = eps.find(e => e.direction === 'in' && e.type === 'bulk'), outEp = eps.find(e => e.direction === 'out' && e.type === 'bulk');
      if (inEp && outEp) return { inEp: inEp.endpointNumber, outEp: outEp.endpointNumber };
    }
    throw new Error('no bulk endpoints found');
  }

  async function openCh340(dev, baud, opts) {
    const log = opts.log || (() => {});
    const nums = dev.configuration.interfaces.map(i => i.interfaceNumber);
    for (const n of nums) await claimIface(dev, n, log);
    const ep = await endpoints(dev, nums.slice().reverse());
    const out = (request, value, index) => dev.controlTransferOut({ requestType: 'vendor', recipient: 'device', request, value, index });
    const inn = async (request, value, index, len) => { try { await dev.controlTransferIn({ requestType: 'vendor', recipient: 'device', request, value, index }, len); } catch (e) { log('CH340 read ' + hex(request) + ' ignored: ' + e.message); } };
    const setBaud = async () => {
      const b = CH340_BAUD[baud]; if (!b) throw new Error('baud rate ' + baud + ' not in table');
      await out(0x9a, 0x1312, b[0]); await out(0x9a, 0x0f2c, b[1]);
    };
    const setLines = (dtr, rts) => out(0xa4, (~((dtr ? 1 << 5 : 0) | (rts ? 1 << 6 : 0))) & 0xffff, 0);
    await inn(0x5f, 0, 0, 2);
    await out(0xa1, 0, 0);
    await setBaud();
    await inn(0x95, 0x2518, 0, 2);
    await out(0x9a, 0x2518, 0x00c3);                   // 8 data bits, RX and TX on
    await inn(0x95, 0x0706, 0, 2);
    await out(0xa1, 0x501f, 0xd90a);
    await setBaud();
    await setLines(false, false);                      // no board reset when we connect
    log('CH340 ready at ' + baud + ' baud');
    return { kind: 'CH340', ep, setLines };
  }

  async function openCdc(dev, baud, opts) {
    const log = opts.log || (() => {});
    let ctrl = null, data = null;
    for (const i of dev.configuration.interfaces) {
      const c = i.alternates[0].interfaceClass; if (c === 0x02) ctrl = i; if (c === 0x0a) data = i;
    }
    if (!data) throw new Error('no CDC serial interface (class 10) on this device');
    if (ctrl) await claimIface(dev, ctrl.interfaceNumber, log);
    await claimIface(dev, data.interfaceNumber, log);
    const ep = await endpoints(dev, [data.interfaceNumber]);
    const ci = ctrl ? ctrl.interfaceNumber : 0;
    const lc = new Uint8Array([baud & 255, (baud >> 8) & 255, (baud >> 16) & 255, (baud >> 24) & 255, 0, 0, 8]);
    await dev.controlTransferOut({ requestType: 'class', recipient: 'interface', request: 0x20, value: 0, index: ci }, lc);
    const setLines = (dtr, rts) => dev.controlTransferOut({ requestType: 'class', recipient: 'interface', request: 0x22, value: (dtr ? 1 : 0) | (rts ? 2 : 0), index: ci });
    await setLines(true, true);                        // this Arduino USB chip needs DTR on; the board restarts once
    log('CDC-ACM ready at ' + baud + ' baud');
    return { kind: 'CDC', ep, setLines };
  }

  /** Open an already-permitted USB device. Returns a port object. */
  async function open(dev, opts = {}) {
    const baud = opts.baud || 9600, log = opts.log || (() => {});
    await dev.open();
    if (dev.configuration === null) await dev.selectConfiguration(1);
    log('USB device ' + hex(dev.vendorId) + ':' + hex(dev.productId));
    const drv = dev.vendorId === 0x1a86 ? await openCh340(dev, baud, opts) : await openCdc(dev, baud, opts);
    const port = { kind: drv.kind, device: dev, ready: true, bytesIn: 0, error: null };
    let running = true, buf = '';
    const dec = new TextDecoder();
    port.write = async data => { if (!running) throw new Error('port closed'); await dev.transferOut(drv.ep.outEp, enc(data)); };
    port.close = async () => { running = false; port.ready = false; try { await dev.close(); } catch (e) {} };
    (async () => {
      while (running) {
        try {
          const r = await dev.transferIn(drv.ep.inEp, 64);
          if (r.status === 'ok' && r.data && r.data.byteLength) {
            port.bytesIn += r.data.byteLength; buf += dec.decode(r.data);
            let k; while ((k = buf.indexOf('\n')) >= 0) { const line = buf.slice(0, k).trim(); buf = buf.slice(k + 1); if (line && opts.onLine) opts.onLine(line); }
            if (buf.length > 400) buf = '';
          } else if (r.status === 'stall') { await dev.clearHalt('in', drv.ep.inEp); }
        } catch (e) { if (running) { port.ready = false; port.error = e.message; if (opts.onClose) opts.onClose(e); } running = false; }
      }
    })();
    // some boards stay silent until DTR/RTS are on: if nothing arrives, switch them on (the board restarts once)
    setTimeout(async () => { if (running && port.bytesIn === 0) { try { await drv.setLines(true, true); log('No data yet, DTR/RTS switched on'); } catch (e) {} } }, opts.idleDtrMs || 3000);
    return port;
  }

  const request = () => navigator.usb.requestDevice({ filters: FILTERS });
  async function known() { return (await navigator.usb.getDevices()).filter(d => VENDORS.includes(d.vendorId)); }
  return { supported, request, known, open, VENDORS };
})();
if (typeof module !== 'undefined') module.exports = UsbSerial;
