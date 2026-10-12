#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include "../firmware/kenny_mobile/usb_protocol.h"

mobile::UsbKind parse(const char* input, mobile::Command& command) {
  char line[96];
  assert(strlen(input) < sizeof(line));
  strcpy(line, input);
  return mobile::parseUsb(line, command);
}

int main() {
  using mobile::UsbKind;
  mobile::Command command;
  assert(parse("HELLO", command) == UsbKind::Hello);
  assert(parse("STATUS", command) == UsbKind::Status);
  assert(parse("ARM", command) == UsbKind::Arm);
  assert(parse("STOP", command) == UsbKind::Stop);
  assert(parse("V 123 1 -0.03 0.20", command) == UsbKind::Drive);
  mobile::State state;
  mobile::Command arm; arm.kind = mobile::Kind::Arm; arm.lease = 123; arm.receivedMs = 100;
  assert(state.apply(arm, 100, false));
  command.receivedMs = 110;
  assert(state.apply(command, 110, false));
  assert(!state.apply(command, 120, false));  // Replayed sequence rejected.
  assert(parse("V 456 2 0.03 0", command) == UsbKind::Drive);
  command.receivedMs = 120;
  assert(!state.apply(command, 120, false));  // Another transport cannot take lease.
  state.tick(410, false);
  assert(!state.armed && (state.faults & mobile::WATCHDOG));
  for (const char* bad : {"", "ARM 1", "STOP extra", "V 0 1 0 0", "V 1 1 nan 0",
       "V 1 1 0 inf", "V 1 1 0.11 0", "V 1 1 0 0.61", "V -1 1 0 0",
       "V 1 4294967296 0 0", "V 1 1 0", "V 1 1 0 0 extra"})
    assert(parse(bad, command) == UsbKind::Invalid);
  puts("USB protocol, shared lease, replay and watchdog tests passed");
}
