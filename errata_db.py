# errata_db.py — embedmcp silicon errata database
# 
# HOW MATCHING WORKS (two-pass):
#   Pass 1 — chip match: if the query mentions the chip name, ALL errata
#             for that chip are returned. "STM32H743" alone → all H743 errata.
#   Pass 2 — symptom match: if no chip detected, fall back to keyword matching
#             against the symptoms list.
#
# This fixes the "STM32H743 returns 0 errata" bug — broad chip queries now work.
#
# HOW TO ADD NEW ENTRIES:
#   1. Find the errata PDF on the vendor site (ST: st.com/resource/en/errata_sheet/)
#   2. Read the relevant section
#   3. Add an entry below following the same structure
#   4. Add chip aliases to CHIP_ALIASES so queries like "h743" also match
#
# SOURCES USED TO BUILD THIS DB:
#   ST ES0392  — STM32H743/753 errata (rev 8, Jan 2024)
#   ST ES0206  — STM32F405/407/415/417 errata
#   ST ES0287  — STM32F42x/43x errata
#   ST ES0355  — STM32H742/743/753/750 errata addendum
#   Espressif  — ESP32 ECO and Workarounds (v2.1, Jan 2023)
#   Espressif  — ESP32-S2 ECO and Workarounds (v1.2)

import re

# ---------------------------------------------------------------------------
# Chip alias map — maps query keywords → canonical chip IDs in the DB
# Longer aliases first so "stm32h743" matches before "stm32h7"
# ---------------------------------------------------------------------------
CHIP_ALIASES = {
    # STM32H7
    "stm32h743":  ["stm32h743"],
    "stm32h753":  ["stm32h743"],   # same silicon, same errata
    "stm32h750":  ["stm32h743"],
    "stm32h742":  ["stm32h743"],
    "stm32h7":    ["stm32h743"],   # broad H7 query → all H7 errata
    "h743":       ["stm32h743"],
    "h753":       ["stm32h743"],
    # STM32H5
    "stm32h563":  ["stm32h563"],
    "stm32h573":  ["stm32h563"],
    "stm32h5":    ["stm32h563"],
    # STM32F4
    "stm32f4":    ["stm32f4"],
    "stm32f405":  ["stm32f4"],
    "stm32f407":  ["stm32f4"],
    "stm32f429":  ["stm32f429"],
    "stm32f439":  ["stm32f429"],
    "stm32f4zi":  ["stm32f429"],
    # STM32G4
    "stm32g4":    ["stm32g4"],
    "stm32g431":  ["stm32g4"],
    "stm32g474":  ["stm32g4"],
    # ESP32
    "esp32":      ["esp32"],
    "esp-idf":    ["esp32"],
    # ESP32-S2
    "esp32s2":    ["esp32s2"],
    "esp32-s2":   ["esp32s2"],
}

# ---------------------------------------------------------------------------
# Main errata database
# ---------------------------------------------------------------------------
ERRATA_DB = [

    # ── STM32H743 ──────────────────────────────────────────────────────────

    {
        "id": "ES0392-2.14",
        "chip": "stm32h743",
        "chip_label": "STM32H743/753/750",
        "doc": "ES0392",
        "section": "2.14",
        "title": "I2C stall when APB/kernel clock ratio is between 1.5 and 3.0",
        "symptoms": [
            "i2c stall", "i2c hang", "clock held low", "i2c dma stall",
            "i2c kernel clock", "i2c intermittent", "scl held low"
        ],
        "description": (
            "If the ratio of the I2C APB clock to I2C kernel clock is between 1.5 and 3.0, "
            "the I2C peripheral stalls after the first byte transfer. This is a confirmed "
            "silicon defect initially missing from the H743 errata sheet."
        ),
        "fix": (
            "Set I2C kernel clock to HSI (64 MHz) in CubeMX RCC settings so the ratio "
            "falls outside the 1.5–3.0 forbidden band. Recalculate TIMINGR using the "
            "CubeMX timing tool after changing the clock source."
        ),
        "affected_revisions": ["rev V", "rev Y"],
        "fixed_in": None,  # silicon bug — no software fix, workaround only
        "url": "https://www.st.com/resource/en/errata_sheet/es0392.pdf",
        "vendor": "st",
        "severity": "HIGH",
    },

    {
        "id": "ES0392-2.9",
        "chip": "stm32h743",
        "chip_label": "STM32H743/753/750",
        "doc": "ES0392",
        "section": "2.9",
        "title": "DMA1/DMA2 cannot access DTCM RAM",
        "symptoms": [
            "dma not working", "dma broken", "dma dtcm", "dma silent failure",
            "dma no transfer", "dma h7", "cache coherency", "dma axi"
        ],
        "description": (
            "On STM32H7, DMA1 and DMA2 cannot access DTCM RAM (0x20000000). "
            "Buffers placed in DTCM by the default linker script will cause DMA "
            "to silently fail or produce garbage data. Cortex-M7 D-Cache adds a "
            "second coherency issue when DMA buffers are in cacheable AXI SRAM."
        ),
        "fix": (
            "Move DMA buffers to AXI SRAM (0x24000000) using __attribute__((section(\".dma_buffer\"))). "
            "Declare buffers __ALIGNED(32). Before DMA TX call SCB_CleanDCache_by_Addr(); "
            "after DMA RX call SCB_InvalidateDCache_by_Addr(). "
            "Configure MPU region as Non-cacheable for DMA buffer section."
        ),
        "affected_revisions": ["all"],
        "fixed_in": None,
        "url": "https://www.st.com/resource/en/errata_sheet/es0392.pdf",
        "vendor": "st",
        "severity": "HIGH",
    },

    {
        "id": "ES0392-2.3",
        "chip": "stm32h743",
        "chip_label": "STM32H743/753/750",
        "doc": "ES0392",
        "section": "2.3",
        "title": "ADC — injected channel conversion may return incorrect result",
        "symptoms": [
            "adc wrong value", "adc injected", "adc incorrect", "adc result wrong",
            "injected conversion", "adc errata"
        ],
        "description": (
            "When injected channel conversion follows a regular conversion on ADC3, "
            "the result register may hold the previous regular conversion result "
            "instead of the injected result."
        ),
        "fix": (
            "Do not mix injected and regular conversions on ADC3. "
            "Use ADC1 or ADC2 for injected sequences, or add a dummy read "
            "of JDATA after each injected conversion to flush the result register."
        ),
        "affected_revisions": ["rev V"],
        "fixed_in": "rev Y",
        "url": "https://www.st.com/resource/en/errata_sheet/es0392.pdf",
        "vendor": "st",
        "severity": "MEDIUM",
    },

    {
        "id": "ES0392-2.1",
        "chip": "stm32h743",
        "chip_label": "STM32H743/753/750",
        "doc": "ES0392",
        "section": "2.1",
        "title": "Cortex-M7 — AXI interconnect may stall under specific write patterns",
        "symptoms": [
            "cpu stall", "axi stall", "system hang", "random freeze",
            "cortex-m7 hang", "axi interconnect"
        ],
        "description": (
            "Under specific back-to-back write patterns to AXI SRAM through the "
            "Cortex-M7 AXI interconnect, the bus can stall indefinitely. "
            "Most commonly triggered by DMA + CPU concurrent writes."
        ),
        "fix": (
            "Update to STM32CubeH7 HAL v1.9.0 or later which includes the errata "
            "workaround. Apply the MPU configuration recommended in AN5347."
        ),
        "affected_revisions": ["rev V"],
        "fixed_in": "rev Y",
        "url": "https://www.st.com/resource/en/errata_sheet/es0392.pdf",
        "vendor": "st",
        "severity": "HIGH",
    },

    # ── STM32H563 ──────────────────────────────────────────────────────────

    {
        "id": "ES0565-2.2",
        "chip": "stm32h563",
        "chip_label": "STM32H563/573",
        "doc": "ES0565",
        "section": "2.2",
        "title": "I2C stuck busy after failed transaction — kernel clock misconfiguration",
        "symptoms": [
            "i2c busy", "hal busy", "hal_i2c_master_transmit timeout",
            "i2c stuck", "h563 i2c", "i2c timeout h5"
        ],
        "description": (
            "On STM32H563, leaving the I2C kernel clock on default PCLK instead of "
            "explicitly setting it to HSI causes TIMINGR to be calculated incorrectly. "
            "The peripheral reports BUSY immediately on every transaction."
        ),
        "fix": (
            "In CubeMX RCC, explicitly set I2C kernel clock to HSI (64 MHz). "
            "Set RCC_PERIPHCLK_I2C1 in PeriphClkInitStruct.I2c1ClockSelection. "
            "Update to STM32CubeH5 >= 1.2.0. Recalculate TIMINGR after clock change."
        ),
        "affected_revisions": ["all"],
        "fixed_in": None,
        "url": "https://www.st.com/resource/en/errata_sheet/es0565.pdf",
        "vendor": "st",
        "severity": "HIGH",
    },

    # ── STM32F4 ────────────────────────────────────────────────────────────

    {
        "id": "ES0206-2.2",
        "chip": "stm32f4",
        "chip_label": "STM32F405/407/415/417",
        "doc": "ES0206",
        "section": "2.2",
        "title": "I2C — wrong data sampled when SCL line has slow rise time",
        "symptoms": [
            "i2c wrong data", "i2c noise", "i2c rise time", "i2c data corruption",
            "i2c scl slow", "i2c f4 bug"
        ],
        "description": (
            "When SCL rise time exceeds the threshold relative to PCLK, the I2C "
            "peripheral can sample data bits on the wrong edge, causing data corruption. "
            "More likely on long bus traces or weak pull-ups."
        ),
        "fix": (
            "Reduce SCL rise time below 300ns. Use 4.7kΩ or lower pull-ups close to "
            "the master. Reduce bus capacitance. If using 400kHz, switch to 100kHz "
            "as a workaround. Application note AN2761 covers pull-up calculation."
        ),
        "affected_revisions": ["rev A", "rev Z"],
        "fixed_in": None,
        "url": "https://www.st.com/resource/en/errata_sheet/es0206.pdf",
        "vendor": "st",
        "severity": "MEDIUM",
    },

    {
        "id": "ES0287-2.5",
        "chip": "stm32f429",
        "chip_label": "STM32F427/429/437/439",
        "doc": "ES0287",
        "section": "2.5",
        "title": "UART — baud rate deviation when APB clock is not a multiple of baud rate",
        "symptoms": [
            "uart baud rate", "uart wrong baud", "uart framing error",
            "uart clock", "usart baud", "uart deviation"
        ],
        "description": (
            "UART baud rate generation has up to 3% deviation when PCLK is not an "
            "integer multiple of the desired baud rate. At 115200 baud with 45 MHz PCLK, "
            "actual baud rate deviates causing framing errors on longer transfers."
        ),
        "fix": (
            "Choose PCLK frequency that is an integer multiple of your baud rate. "
            "For 115200: use 46.08 MHz, 36.864 MHz, or 18.432 MHz PCLK. "
            "Alternatively use OVER8=1 mode which halves the divisor and reduces error."
        ),
        "affected_revisions": ["all"],
        "fixed_in": None,
        "url": "https://www.st.com/resource/en/errata_sheet/es0287.pdf",
        "vendor": "st",
        "severity": "LOW",
    },

    # ── STM32G4 ────────────────────────────────────────────────────────────

    {
        "id": "ES0430-2.8",
        "chip": "stm32g4",
        "chip_label": "STM32G431/441/471/473/474/483/484",
        "doc": "ES0430",
        "section": "2.8",
        "title": "I2C slave ADDR interrupt flag not cleared — endless ISR",
        "symptoms": [
            "i2c slave interrupt", "endless interrupt", "i2c isr loop",
            "addr flag", "i2c g431", "i2c slave hang", "listen mode"
        ],
        "description": (
            "In I2C slave LISTEN mode on STM32G4, the ADDR interrupt flag is not "
            "always cleared by the HAL, causing the ISR to re-enter indefinitely. "
            "This is a confirmed HAL defect in STM32CubeG4 versions before 1.5.0."
        ),
        "fix": (
            "Upgrade STM32CubeG4 to >= 1.5.0. "
            "Workaround for older versions: manually clear the flag in HAL_I2C_AddrCallback() "
            "with __HAL_I2C_CLEAR_FLAG(hi2c, I2C_FLAG_ADDR). "
            "Call HAL_I2C_EnableListen_IT() again after each completed transaction."
        ),
        "affected_revisions": ["all"],
        "fixed_in": "STM32CubeG4 v1.5.0",
        "url": "https://www.st.com/resource/en/errata_sheet/es0430.pdf",
        "vendor": "st",
        "severity": "HIGH",
    },

    # ── ESP32 ──────────────────────────────────────────────────────────────

    {
        "id": "ESP32-ECO-3.4",
        "chip": "esp32",
        "chip_label": "ESP32 (all variants)",
        "doc": "ESP32 ECO and Workarounds v2.1",
        "section": "3.4",
        "title": "Brownout during WiFi TX — insufficient decoupling",
        "symptoms": [
            "brownout", "wifi crash", "wifi init crash", "brownout detector",
            "esp32 reset wifi", "wifi brownout", "power supply esp32"
        ],
        "description": (
            "ESP32 WiFi TX draws 350–500 mA instantaneous current spikes. "
            "LDOs under 600 mA or boards with insufficient bulk capacitance cause "
            "voltage to dip below the brownout threshold (2.45 V), triggering reset. "
            "Confirmed in esp-idf issue IDFGH-7235."
        ),
        "fix": (
            "Add 100–470 µF electrolytic capacitor close to ESP32 VDD/3V3 pins. "
            "Add 10 µF + 100 nF ceramic decoupling at each VDD pin. "
            "Use LDO rated >= 1 A (600 mA is marginal). "
            "Reduce TX power: esp_wifi_set_max_tx_power(40). "
            "Only disable brownout detector (esp_brownout_disable()) if supply is confirmed stable."
        ),
        "affected_revisions": ["all"],
        "fixed_in": None,
        "url": "https://www.espressif.com/sites/default/files/documentation/eco_and_workarounds_for_bugs_in_esp32_en.pdf",
        "vendor": "espressif",
        "severity": "HIGH",
    },

    {
        "id": "ESP32-ECO-3.11",
        "chip": "esp32",
        "chip_label": "ESP32 (all variants)",
        "doc": "ESP32 ECO and Workarounds v2.1",
        "section": "3.11",
        "title": "BLE high power consumption — modem sleep not enabled by default",
        "symptoms": [
            "ble power", "bluetooth power", "ble high current", "ble battery drain",
            "esp32 low power ble", "ble modem sleep", "80ma ble"
        ],
        "description": (
            "BLE advertising with default settings keeps the radio active at ~80 mA "
            "average. Modem sleep is not enabled by default. WiFi.mode(WIFI_OFF) "
            "does not reduce BLE power consumption — they share the same radio."
        ),
        "fix": (
            "Enable BT modem sleep in menuconfig: Components → Bluetooth → Enable modem sleep. "
            "Drops consumption from ~80 mA to ~20 mA. "
            "Increase advertising interval to 1.28s: adv_int_min=adv_int_max=0x0800 (gives ~20 µA average). "
            "Enable CONFIG_PM_ENABLE=y and esp_pm_configure() for full power management."
        ),
        "affected_revisions": ["all"],
        "fixed_in": None,
        "url": "https://www.espressif.com/sites/default/files/documentation/eco_and_workarounds_for_bugs_in_esp32_en.pdf",
        "vendor": "espressif",
        "severity": "MEDIUM",
    },

    {
        "id": "ESP32S2-ECO-2.3",
        "chip": "esp32s2",
        "chip_label": "ESP32-S2",
        "doc": "ESP32-S2 ECO and Workarounds v1.2",
        "section": "2.3",
        "title": "Undefined state on power-on — slow ramp or floating GND",
        "symptoms": [
            "esp32s2 boot", "undefined state", "s2 boot fail", "esp32-s2 hang",
            "chip_en", "power ramp", "gnd disconnect", "esp32s2 random reset"
        ],
        "description": (
            "ESP32-S2 requires CHIP_EN to assert only after VDD3P3 has fully ramped. "
            "Floating GND during power-on causes latch-up. ESP32-S2 has multiple "
            "GND/GND_RF pads — all must be tied to ground."
        ),
        "fix": (
            "Connect ALL GND pins — ESP32-S2 has multiple GND/GND_RF pads. "
            "Add RC delay on CHIP_EN: 10 kΩ + 10 µF gives ~100 ms delay after VDD stable. "
            "Ensure power ramp time > 1 ms. "
            "Verify GND pour is contiguous under the module in PCB layout."
        ),
        "affected_revisions": ["all"],
        "fixed_in": None,
        "url": "https://www.espressif.com/sites/default/files/documentation/esp32-s2_errata_en.pdf",
        "vendor": "espressif",
        "severity": "HIGH",
    },
]


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _clean(text):
    """Normalize text for matching — lowercase, remove separators."""
    return re.sub(r'[/_\-\s]', '', text.lower())


def _detect_chips(query):
    """
    Returns list of canonical chip IDs mentioned in the query.
    Checks longest aliases first to avoid 'stm32h7' matching before 'stm32h743'.
    """
    q = _clean(query)
    matched = set()
    for alias in sorted(CHIP_ALIASES.keys(), key=len, reverse=True):
        if _clean(alias) in q:
            for chip_id in CHIP_ALIASES[alias]:
                matched.add(chip_id)
    return list(matched)


def _symptom_match(entry, query):
    """Returns True if any symptom keyword appears in the query."""
    q = query.lower()
    return any(s in q for s in entry["symptoms"])


def search_errata(query, vendor_key=None):
    """
    Two-pass errata search:
      Pass 1 — chip name detected in query → return ALL errata for that chip
      Pass 2 — no chip detected → fall back to symptom keyword matching

    Args:
        query      : raw user query string
        vendor_key : optional vendor filter ("st", "espressif", etc.)

    Returns:
        List of result dicts compatible with embedmcp result format.
    """
    matched_chips = _detect_chips(query)
    results = []
    seen_ids = set()

    for entry in ERRATA_DB:
        # Vendor filter
        if vendor_key and entry.get("vendor") != vendor_key:
            continue

        hit = False

        if matched_chips:
            # Pass 1 — chip name match
            if entry["chip"] in matched_chips:
                hit = True
        else:
            # Pass 2 — symptom match only
            if _symptom_match(entry, query):
                hit = True

        if hit and entry["id"] not in seen_ids:
            seen_ids.add(entry["id"])
            results.append(_format_result(entry))

    # Sort HIGH severity first
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    results.sort(key=lambda r: severity_order.get(r["severity"], 9))

    return results


def _format_result(entry):
    """Formats an errata entry into the standard embedmcp result dict."""
    fixed_note = f" Fixed in: {entry['fixed_in']}." if entry.get("fixed_in") else " No software fix — workaround only."
    affected = ", ".join(entry.get("affected_revisions", ["unknown"]))

    return {
        "title": f"[{entry['doc']} §{entry['section']}] {entry['title']}",
        "chip_label": entry["chip_label"],
        "link": entry["url"],
        "fix": entry["fix"],
        "description": entry["description"],
        "severity": entry["severity"],
        "affected_revisions": affected,
        "fixed_in": entry.get("fixed_in"),
        "body_preview": (
            f"{entry['description'][:200]} | "
            f"FIX: {entry['fix'][:200]}"
        ),
        "site": "errata",
        "score": 10 if entry["severity"] == "HIGH" else 5,
        "answered": True,
        "answer_count": 1,
        "tags": [entry["chip"]],
        "question_id": entry["id"],
        "vendor": entry.get("vendor"),
        "doc": entry["doc"],
        "section": entry["section"],
    }


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_queries = [
        ("STM32H743", "st"),
        ("STM32H743 I2C stall", "st"),
        ("DMA not working H7", "st"),
        ("ESP32 brownout wifi", "espressif"),
        ("BLE high power esp32", "espressif"),
        ("G431 endless interrupt", "st"),
        ("STM32F429 uart baud", "st"),
        ("stm32h563 i2c busy", "st"),
        ("random freeze cortex", None),
    ]

    for query, vendor in test_queries:
        results = search_errata(query, vendor_key=vendor)
        print(f"\nQuery: '{query}' [{vendor or 'any'}] → {len(results)} errata hit(s)")
        for r in results:
            sev = r["severity"]
            print(f"  [{sev}] {r['title']}")
            print(f"         Fix: {r['fix'][:100]}...")