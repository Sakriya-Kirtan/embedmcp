from dotenv import load_dotenv
import os

load_dotenv()

# config.py - expanded with all major embedded vendors

STACK_SITES = {
    "stackoverflow": {
        "site": "stackoverflow",
        "description": "Firmware & software questions"
    },
    "electronics": {
    "site": "electronics"
    }
}

# All the tags we care about across the embedded ecosystem
# These are used later when we build smarter search routing
EMBEDDED_TAGS = [
    # MCUs & processors
    "stm32", "esp32", "esp8266", "arduino", "raspberry-pi", "rp2040",
    "avr", "pic", "arm", "cortex-m", "risc-v", "renesas", "nxp",
    "ti-launchpad", "msp430", "nordic-nrf", "nrf52",
    
    # Protocols
    "i2c", "spi", "uart", "can-bus", "usb", "modbus", "mqtt",
    "ethernet", "lin-bus", "rs485",
    
    # RTOS & firmware
    "freertos", "zephyr", "embedded-linux", "bare-metal", "rtos",
    "bootloader", "dma", "interrupt",
    
    # Hardware & EE
    "pcb", "pcb-design", "power-supply", "mosfet", "op-amp",
    "adc", "dac", "pwm", "motor-driver", "battery-management"
]

RESULTS_PER_SITE = 5
STACK_API_URL = "https://api.stackexchange.com/2.3"
MIN_SCORE = 0
# Vendor-specific resources
# We'll use these to route queries smartly —
# e.g. "STM32 HAL bug" → also search ST's own community
VENDOR_RESOURCES = {
    "st": {
        "name": "STMicroelectronics",
        "community_url": "https://community.st.com",
        "products": ["stm32", "stm8", "hal", "cube"],
        "so_tags": ["stm32", "stm32f4", "stm32h7", "stm32cubemx"]
    },
    "espressif": {
        "name": "Espressif (ESP32/ESP8266)",
        "community_url": "https://www.esp32.com",
        "products": ["esp32", "esp8266", "esp-idf", "esphome"],
        "so_tags": ["esp32", "esp8266", "esp-idf", "arduino-esp32"]
    },
    "arduino": {
        "name": "Arduino",
        "community_url": "https://forum.arduino.cc",
        "products": ["arduino", "uno", "mega", "nano", "due"],
        "so_tags": ["arduino", "arduino-uno", "arduino-ide"]
    },

    "raspberrypi": {
        "name": "Raspberry Pi",
        "community_url": "https://forums.raspberrypi.com",
        "products": ["raspberry-pi", "rp2040", "pico", "raspberrypi"],
        "so_tags": ["raspberry-pi", "raspberry-pi-pico", "rp2040"]
    },
    "renesas": 
    {
        "name": "Renesas",
        "community_url": "https://en-support.renesas.com/knowledgeBase",
        "products": ["rzg", "rzg3", "rzg3e", "ra", "rx", "rl78", "synergy"],
        "aliases": [
            "rz/g",
            "rz-g",
            "rzv",
            "rz/v",
            "rzg2l",
            "rzg3e",
            "r9a"
        ],

        "so_tags": [
            "renesas",
            "rx62n",
            "e2studio"
        ]
    },
    "nordic": {
        "name": "Nordic Semiconductor (nRF)",
        "community_url": "https://devzone.nordicsemi.com",
        "products": ["nrf52", "nrf53", "nrf91", "zephyr", "ble"],
        "so_tags": ["nordic-nrf", "nrf52", "ble", "zephyr-rtos"]
    },
    "nxp": {
        "name": "NXP Semiconductors",
        "community_url": "https://community.nxp.com",
        "products": ["lpc", "kinetis", "imx", "s32"],
        "so_tags": ["nxp", "lpc1768", "freescale", "imx6"]
    },
    "ti": {
        "name": "Texas Instruments",
        "community_url": "https://e2e.ti.com",
        "products": ["msp430", "tiva-c", "cc32xx", "launchpad"],
        "so_tags": ["ti-launchpad", "msp430", "tiva-c", "cc3200"]
    }
}