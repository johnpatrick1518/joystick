"""Exercise the actual mobile page in Chromium against a simulated ESP32 API.

Requires playwright and its Chromium browser. No ESP32 or motor is actuated.
Writes a mock-telemetry preview to artifacts/mobile/joystick-preview.png.
"""
from functools import partial
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-previews', action='store_true', help='Update docs screenshots after successful checks')
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(REPO / "firmware/kenny_mobile/web")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state = dict(armed=False, estop=False, ready=True, faults=0, boot=42, uptime=12000,
                 wiring="Carrier PCB / MCP23017", estopPin=18, v=0, w=0, cpr=1320,
                 maxV=0.1, maxW=0.6, watchdog=300, counts=[0]*4, rpm=[0]*4, pwm=[0]*4)
    requests = []
    reject_drive = False
    active_lease = 0
    hold_next_drive = False
    held_route = None
    hold_next_arm = False
    held_arm = None
    hold_next_stop = False
    held_stop = None
    hold_next_status = False
    held_status = None
    reject_stop_ack = False

    def api(route):
        nonlocal active_lease, hold_next_drive, held_route, hold_next_arm, held_arm, hold_next_stop, held_stop, hold_next_status, held_status
        path = route.request.url.split("/api/")[-1]
        body = parse_qs(route.request.post_data or "")
        requests.append((path, body))
        code, result = 200, {"ok": True}
        if path == "status":
            result = state
            if hold_next_status:
                hold_next_status = False
                held_status = (route, json.dumps(state))
                return
        elif path == "arm":
            if state["armed"] or state["estop"] or not state["ready"]:
                code, result = 409, {"ok": False, "error": "Controller unavailable"}
            else:
                state["armed"] = True
                active_lease += 1
                result = {"ok": True, "lease": active_lease}
                if hold_next_arm:
                    hold_next_arm = False
                    held_arm = (route, result)
                    return
        elif path == "drive":
            if reject_drive or not state["armed"] or int(body["lease"][0]) != active_lease:
                code, result = 409, {"ok": False}
            else:
                state["v"] = float(body["v"][0]); state["w"] = float(body["w"][0])
                if hold_next_drive and (state['v'] or state['w']):
                    hold_next_drive = False
                    held_route = route
                    return
        elif path == "stop":
            state["armed"] = False; state["v"] = state["w"] = 0
            if reject_stop_ack:
                code, result = 503, {'ok':False, 'error':'Stop acknowledgement unavailable'}
            if hold_next_stop:
                hold_next_stop = False
                held_stop = route
                return
        route.fulfill(status=code, content_type="application/json", body=json.dumps(result))

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
            context.route("**/api/*", api)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.wait_for_function("document.getElementById('connection').textContent.includes('Connected')")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not page.get_by_role("button", name="Arm controller").is_disabled()
            assert not any(path == "drive" for path, _ in requests)
            output = REPO / "artifacts/mobile"
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / "joystick-preview.png"), full_page=True)

            def arm():
                page.wait_for_function("!document.getElementById('arm').disabled")
                page.locator("#arm").click()
                page.wait_for_function("document.getElementById('mode').textContent === 'READY'")

            arm()
            box = page.locator("#pad").bounding_box()
            cx, cy = box["x"] + box["width"]/2, box["y"] + box["height"]/2
            touch = context.new_cdp_session(page)
            touch.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':cx,'y':cy,'id':1}]})
            touch.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':cx,'y':cy-70,'id':1}]})
            page.wait_for_function("parseFloat(document.getElementById('linear').textContent) > 0")
            page.wait_for_timeout(180)
            assert any(path == "drive" and float(body["v"][0]) > 0 for path, body in requests)
            touch.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
            page.wait_for_timeout(160)
            assert state["v"] == 0 and state["w"] == 0

            hold_next_drive = True
            page.mouse.move(cx,cy); page.mouse.down(); page.mouse.move(cx,cy-70)
            page.wait_for_timeout(90)
            assert held_route is not None
            page.mouse.up(); page.wait_for_timeout(50)
            assert state['v'] == 0 and state['w'] == 0  # Release bypasses an outstanding drive request.
            held_route.fulfill(status=409,content_type='application/json',body='{"ok":false}')
            page.wait_for_timeout(80)
            assert page.locator('#mode').inner_text() == 'READY'

            page.mouse.move(cx,cy); page.mouse.down(); page.mouse.move(cx-65,cy)
            page.wait_for_timeout(180)
            assert state["w"] > 0  # Left drag -> positive turn rate.
            page.mouse.up(); page.wait_for_timeout(120)
            page.mouse.move(cx,cy); page.mouse.down(); page.mouse.move(cx,cy+70)
            page.wait_for_timeout(180)
            assert state["v"] < 0
            page.mouse.up()
            page.locator("#stop").click()
            page.wait_for_timeout(120)
            assert not state["armed"]
            assert page.locator("#mode").inner_text() == "DISARMED"

            # A pre-STOP armed status arriving late cannot lock the button again.
            arm()
            hold_next_status = True
            page.wait_for_timeout(550)
            assert held_status is not None
            page.locator('#stop').click()
            page.wait_for_timeout(80)
            assert not page.locator('#arm').is_disabled()
            held_status[0].fulfill(status=200,content_type='application/json',body=held_status[1])
            page.wait_for_timeout(100)
            assert not page.locator('#arm').is_disabled()

            # A failed STOP reply recovers only after fresh disarmed status arrives.
            reject_stop_ack = True
            page.locator('#stop').click()
            page.wait_for_function("!document.getElementById('arm').disabled", timeout=1500)
            assert not state['armed']
            reject_stop_ack = False

            arm()
            page.evaluate("window.dispatchEvent(new Event('blur'))")
            page.wait_for_timeout(160)
            assert not state["armed"]
            arm()
            reject_drive = True
            page.wait_for_function("document.getElementById('mode').textContent === 'DISARMED'")
            page.wait_for_timeout(150)
            assert not state["armed"]
            reject_drive = False
            state["estop"] = True; state["faults"] = 2
            page.wait_for_function("document.getElementById('estop').textContent.includes('OPEN')")
            assert page.locator("#arm").is_disabled()
            assert 'GPIO18' in page.locator('#armReason').inner_text()
            assert 'OPEN' in page.locator('#armReason').inner_text()
            page.locator('#stop').click()
            page.wait_for_timeout(100)
            assert page.locator('#arm').is_disabled()
            assert 'E-stop' in page.locator('#message').inner_text()

            # Master Control presents exactly the speed control and joystick.
            state['estop'] = False; state['faults'] = 0
            page.wait_for_function("document.getElementById('estop').textContent === 'Closed'")
            start = len(requests)
            page.locator('#masterLink').click()
            page.wait_for_function("document.body.classList.contains('master') && document.getElementById('pad').getAttribute('aria-disabled') === 'false'")
            assert page.locator('button:visible').count() == 0
            assert page.locator('a:visible').count() == 0
            assert page.locator('input:visible').count() == 1
            assert page.locator('#limit').is_visible() and page.locator('#pad').is_visible()
            assert not page.locator('header').is_visible()
            assert not page.locator('.details').is_visible()
            assert not page.locator('.outputs').is_visible()
            assert not page.locator('footer').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not any(path == 'arm' for path, _ in requests[start:])
            page.locator('#limit').evaluate("el => { el.value='30'; el.dispatchEvent(new Event('input')); }")
            page.wait_for_timeout(100)
            assert not any(path == 'arm' for path, _ in requests[start:])
            page.screenshot(path=str(output / 'master-control-preview.png'), full_page=True)
            box = page.locator('#pad').bounding_box()
            cx, cy = box['x'] + box['width']/2, box['y'] + box['height']/2
            touch.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':cx,'y':cy,'id':1}]})
            touch.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':cx,'y':cy-90,'id':1}]})
            page.wait_for_function("document.getElementById('mode').textContent === 'DRIVING'")
            page.wait_for_timeout(130)
            assert state['armed'] and 0 < state['v'] <= 0.03
            touch.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
            page.wait_for_timeout(130)
            assert not state['armed'] and state['v'] == 0 and state['w'] == 0
            page.wait_for_function("document.getElementById('pad').getAttribute('aria-disabled') === 'false'")

            # Release BEFORE an ARM response: a late acknowledgement must never drive.
            start = len(requests)
            hold_next_arm = True
            page.mouse.move(cx,cy); page.mouse.down(); page.mouse.move(cx,cy-80)
            page.wait_for_timeout(80)
            assert held_arm is not None
            page.mouse.up(); page.wait_for_timeout(70)
            assert not state['armed']
            held_arm[0].fulfill(status=200,content_type='application/json',body=json.dumps(held_arm[1]))
            page.wait_for_timeout(100)
            assert not state['armed']
            assert not any(path == 'drive' for path, _ in requests[start:])

            # A zero-percent speed setting never generates a nonzero request.
            page.wait_for_function("document.getElementById('pad').getAttribute('aria-disabled') === 'false'")
            page.locator('#limit').evaluate("el => { el.value='0'; el.dispatchEvent(new Event('input')); }")
            page.mouse.move(cx,cy); page.mouse.down(); page.mouse.move(cx,cy-80)
            page.wait_for_function("document.getElementById('mode').textContent === 'DRIVING'")
            page.wait_for_timeout(120)
            assert state['armed'] and state['v'] == 0 and state['w'] == 0
            page.mouse.up(); page.wait_for_timeout(100)
            assert not state['armed']

            # Changing back to diagnostics during a held gesture stops and disarms.
            page.wait_for_function("document.getElementById('pad').getAttribute('aria-disabled') === 'false'")
            page.locator('#limit').evaluate("el => { el.value='50'; el.dispatchEvent(new Event('input')); }")
            page.mouse.move(cx,cy); page.mouse.down(); page.mouse.move(cx,cy-80)
            page.wait_for_function("document.getElementById('mode').textContent === 'DRIVING'")
            page.wait_for_timeout(100)
            hold_next_stop = True
            page.evaluate("location.hash = ''")
            page.wait_for_function("!document.body.classList.contains('master')")
            page.wait_for_timeout(80)
            assert held_stop is not None
            assert not state['armed'] and state['v'] == 0
            page.mouse.up()
            assert page.locator('.details').is_visible()
            # STOP during an outstanding view-change STOP must not permanently lock Arm.
            page.locator('#stop').click()
            page.wait_for_timeout(80)
            held_stop.fulfill(status=200, content_type='application/json', body='{"ok":true}')
            page.wait_for_function("!document.getElementById('arm').disabled", timeout=1500)
            assert not state['armed']
            arm()
            page.locator('#stop').click()
            page.wait_for_function("!document.getElementById('arm').disabled", timeout=1500)

            # Direct bookmarks into Master Control don't arm on page load.
            start = len(requests)
            page.goto(f"http://127.0.0.1:{server.server_port}/#master")
            page.wait_for_function("document.getElementById('pad').getAttribute('aria-disabled') === 'false'")
            assert not any(path == 'arm' for path, _ in requests[start:])
            state['estop'] = True; state['faults'] = 2
            page.wait_for_function("document.getElementById('pad').getAttribute('aria-disabled') === 'true'")
            start = len(requests)
            box = page.locator('#pad').bounding_box()
            page.mouse.click(box['x']+box['width']/2, box['y']+box['height']/2)
            page.wait_for_timeout(100)
            assert not any(path == 'arm' for path, _ in requests[start:])
            # Bare breadboard: absent E-stop/encoder hardware still permits driving.
            state.update(estop=False, faults=0, wiring='Direct GPIO', estopPin=15,
                         estopEnabled=False, encodersEnabled=False, cpr=0)
            page.wait_for_function("document.getElementById('pad').getAttribute('aria-disabled') === 'false'")
            page.mouse.move(box['x']+box['width']/2, box['y']+box['height']/2)
            page.mouse.down()
            page.mouse.move(box['x']+box['width']/2, box['y']+box['height']/2-80)
            page.wait_for_function("document.getElementById('mode').textContent === 'DRIVING'")
            page.wait_for_timeout(130)
            assert state['armed'] and state['v'] > 0
            page.mouse.up()
            page.wait_for_function("document.getElementById('pad').getAttribute('aria-disabled') === 'false'")
            assert not state['armed'] and state['v'] == 0
            page.evaluate("location.hash = ''")
            page.wait_for_function("!document.getElementById('arm').disabled")
            assert page.locator('#estop').inner_text() == 'Disabled'
            assert 'Open-loop breadboard' in page.locator('#feedback').inner_text()
            assert page.locator('#cpr').inner_text() == 'Disabled'
            assert page.locator('#wheels tr').first.locator('td').nth(1).inner_text() == '—'
            assert not errors, errors
            browser.close()
            if args.refresh_previews:
                for name in ('joystick-preview.png', 'master-control-preview.png'):
                    (REPO / 'docs' / name).write_bytes((output / name).read_bytes())
            print("Browser checks passed: STOP/re-arm recovery, stale-status and view-change races, disabled-button reasons, full controller and Master Control regressions; no JS errors")
    finally:
        server.shutdown(); server.server_close()


if __name__ == "__main__":
    main()
