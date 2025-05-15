import re
import time
from datetime import datetime
from pathlib import Path

import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.firefox import GeckoDriverManager


# --- Color Styles ---
# NOTE: for Windows users: ANSI escape codes might not render correctly in older cmd.exe.
class style:  # noqa: N801
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


# --- Configuration Constants ---
CEN_BASE_URL = (
    "https://www.coordinador.cl/operacion/graficos/operacion-real/generacion-real/"
)
# WARNING: This selector is fragile to site changes
DATE_PICKER_ID = "datepicker777-504991_2"
DOWNLOAD_BUTTON_CLASS = "download-file-marginal"
DOWNLOAD_BUTTON_XPATH_FALLBACK = "//a[contains(@class, 'cen_btn') and contains(@class, 'cen_btn-primary') and (contains(text(), 'Descargar Datos') or contains(text(), 'Descargar'))]"


# --- Colored Logging Helpers ---
def _get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log_info(message: str):
    print(f"{style.CYAN}[{_get_timestamp()} INFO]{style.RESET} {message}")


def _log_success(message: str):
    print(f"{style.GREEN}[{_get_timestamp()} SUCCESS]{style.RESET} {message}")


def _log_error(message: str):
    print(f"{style.RED}[{_get_timestamp()} ERROR]{style.RESET} {message}")


def _log_warning(message: str):
    print(f"{style.YELLOW}[{_get_timestamp()} WARNING]{style.RESET} {message}")


# --- Core Functions ---
def initialize_driver_and_navigate(base_download_path="."):
    _log_info("Initializing browser...")
    actual_download_dir = Path(base_download_path).resolve() / "downloads"
    actual_download_dir.mkdir(parents=True, exist_ok=True)
    _log_info(
        f"Download directory set to: {style.YELLOW}{actual_download_dir}{style.RESET}",
    )

    firefox_options = Options()
    firefox_options.set_preference("browser.download.folderList", 2)
    firefox_options.set_preference("browser.download.manager.showWhenStarting", False)
    firefox_options.set_preference("browser.download.dir", str(actual_download_dir))
    firefox_options.set_preference(
        "browser.helperApps.neverAsk.saveToDisk",
        "text/tab-separated-values,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream",
    )
    # firefox_options.add_argument("--headless") # Uncomment for headless operation

    try:
        driver = webdriver.Firefox(
            service=FirefoxService(GeckoDriverManager().install()),
            options=firefox_options,
        )
        _log_info(f"Navigating to {style.BLUE}{CEN_BASE_URL}{style.RESET}...")
        driver.get(CEN_BASE_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "tipo-descarga")),
        )
        _log_success("Page loaded successfully.")
        return driver, actual_download_dir
    except Exception as e:
        _log_error(
            f"During browser initialization or navigation: {type(e).__name__} - {e}",
        )
        return None, None


def set_download_parameters(driver, download_type, year, month, file_format):
    _log_info(
        f"Setting parameters: Type='{style.MAGENTA}{download_type}{style.RESET}', Date='{style.MAGENTA}{month:02d}/{year}{style.RESET}', Format='{style.MAGENTA}{file_format}{style.RESET}'"
    )
    try:
        driver.execute_script(f"""
            var select = document.querySelector('.tipo-descarga');
            select.value = '{download_type}';
            var event = new Event('change', {{ bubbles: true }});
            select.dispatchEvent(event);
        """)
        _log_info(f"Download type set to: {style.MAGENTA}{download_type}{style.RESET}")

        date_picker = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, DATE_PICKER_ID)),
        )
        hidden_input_id = f"{DATE_PICKER_ID}_value"

        month_str_padded = f"{month:02d}"
        date_display_str = f"{month_str_padded}/{year}"
        date_internal_value_str = f"{year}-{month_str_padded}"

        driver.execute_script(
            f"arguments[0].value = '{date_display_str}';",
            date_picker,
        )
        driver.execute_script(
            f"arguments[0].setAttribute('data-date', '{date_internal_value_str}');",
            date_picker,
        )
        hidden_input = driver.find_element(By.ID, hidden_input_id)
        driver.execute_script(
            f"arguments[0].value = '{date_internal_value_str}';",
            hidden_input,
        )

        for el_to_event in [date_picker, hidden_input]:
            driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                el_to_event,
            )
            driver.execute_script(
                "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                el_to_event,
            )

        driver.find_element(By.TAG_NAME, "body").click()
        _log_info(f"Date set to: {style.MAGENTA}{date_display_str}{style.RESET}")
        time.sleep(0.5)

        format_radio = driver.find_element(By.ID, f"tipo-{file_format}")
        driver.execute_script("arguments[0].click();", format_radio)
        _log_info(f"File format set to: {style.MAGENTA}{file_format}{style.RESET}")
        return True
    except (NoSuchElementException, TimeoutException) as e:
        _log_error(
            f"Setting parameters (element not found or timeout): {type(e).__name__} - {e}",
        )
        return False
    except Exception as e:
        _log_error(
            f"Unexpected error while setting parameters: {type(e).__name__} - {e}",
        )
        return False


def click_and_capture_url(driver, year, month, file_format_ext):
    _log_info("Clicking download and attempting to capture URL...")
    month_str_padded = f"{month:02d}"
    generated_url_date_path_segment = f"{month_str_padded}-{year}"
    expected_generated_path_to_check = (
        f"gen_files/keys/{generated_url_date_path_segment}.{file_format_ext}"
    )

    original_window = driver.current_window_handle
    num_windows_before_click = len(driver.window_handles)

    try:
        try:
            download_button = driver.find_element(By.CLASS_NAME, DOWNLOAD_BUTTON_CLASS)
            _log_info(
                f"Found download button by class name '{style.YELLOW}{DOWNLOAD_BUTTON_CLASS}{style.RESET}'",
            )
        except NoSuchElementException:
            download_button = driver.find_element(
                By.XPATH,
                DOWNLOAD_BUTTON_XPATH_FALLBACK,
            )
            _log_info(
                f"Found download button by XPath: '{style.YELLOW}{DOWNLOAD_BUTTON_XPATH_FALLBACK}{style.RESET}'",
            )

        driver.execute_script("arguments[0].click();", download_button)
        _log_info("Download button clicked.")

        WebDriverWait(driver, 15).until(
            EC.number_of_windows_to_be(num_windows_before_click + 1),
        )

        new_window = next(
            window for window in driver.window_handles if window != original_window
        )
        driver.switch_to.window(new_window)
        _log_info(
            f"Switched to new window/tab (Title: '{style.MAGENTA}{driver.title}{style.RESET}')",
        )

        _log_info(
            f"Waiting for URL from browser with segment: '{style.BLUE}{expected_generated_path_to_check}{style.RESET}' and 'user_key'",
        )
        WebDriverWait(driver, 15).until(
            lambda d: "user_key" in d.current_url
            and expected_generated_path_to_check in d.current_url.lower(),
        )
        captured_url = driver.current_url
        _log_success(f"URL captured: {style.BLUE}{captured_url}{style.RESET}")

        driver.close()
        driver.switch_to.window(original_window)
        return captured_url
    except (NoSuchElementException, TimeoutException) as e:
        _log_error(
            f"Clicking download or capturing URL (element not found or timeout): {type(e).__name__} - {e}",
        )
        if (
            driver.current_window_handle != original_window
            and len(driver.window_handles) > 1
        ):
            # ... (error recovery for window handles as before)
            pass
        return None
    except Exception as e:
        _log_error(f"Unexpected error during URL capture: {type(e).__name__} - {e}")
        return None


def attempt_file_download(
    url_to_try,
    year,
    month,
    file_format_ext,
    download_dir,
    attempt_desc="",
):
    _log_info(f"{attempt_desc}Downloading from: {style.BLUE}{url_to_try}{style.RESET}")
    try:
        response = requests.get(url_to_try, timeout=60)
        response.raise_for_status()

        suffix = "_correctedURL" if "corrected" in attempt_desc.lower() else ""
        filename = f"CEN_data_{year}_{month:02d}{suffix}.{file_format_ext}"
        filepath = download_dir / filename

        with open(filepath, "wb") as f:
            f.write(response.content)
        _log_success(f"File saved to {style.YELLOW}{filepath}{style.RESET}")
        return True, None
    except requests.exceptions.HTTPError as e:
        _log_error(
            f"{attempt_desc}Request FAILED (HTTPError {style.BOLD}{e.response.status_code}{style.RESET}): {url_to_try}",
        )
        return False, e.response.status_code
    except requests.exceptions.RequestException as e:
        _log_error(
            f"{attempt_desc}Request FAILED (RequestException): {type(e).__name__} - {e}",
        )
        return False, None


def download_data_with_correction(
    captured_url,
    year,
    month,
    file_format_ext,
    download_dir,
):
    if not captured_url:
        _log_error("No URL provided for download_data_with_correction.")
        return False

    _log_info(f"Processing download for URL: {style.BLUE}{captured_url}{style.RESET}")
    success, status_code = attempt_file_download(
        captured_url,
        year,
        month,
        file_format_ext,
        download_dir,
        "Attempt 1 (Captured URL) ",
    )
    if success:
        return True

    if status_code == 404:
        _log_warning("Captured URL resulted in 404. Attempting to correct URL format.")

        pattern_str = (
            r"(?P<base_url>https://[^/]+/api/v1/static/gen_files/keys/)"
            r"(?P<mm>\d{2})-(?P<yyyy>\d{4})"
            rf"\.(?P<ext>{re.escape(file_format_ext)})"
            r"\?user_key=(?P<key>[a-zA-Z0-9]+)"
        )
        match = re.match(pattern_str, captured_url)

        if match:
            gd = match.groupdict()
            api_expected_date_segment = f"{gd['yyyy']}-{int(gd['mm'])}"
            corrected_download_url = f"{gd['base_url']}{api_expected_date_segment}.{gd['ext']}?user_key={gd['key']}"

            success_corrected, _ = attempt_file_download(
                corrected_download_url,
                year,
                month,
                file_format_ext,
                download_dir,
                "Attempt 2 (Corrected URL) ",
            )
            return success_corrected
        else:
            _log_error(
                "Could not parse the captured URL with regex to attempt correction.",
            )
            return False
    return False


# --- Orchestration Functions ---
def download_single_cen_file(
    driver,
    download_dir,
    download_type,
    year,
    month,
    file_format_ext,
):
    _log_info(
        f"--- {style.BOLD}Starting process for {style.MAGENTA}{month:02d}/{year}{style.RESET} (Format: {style.MAGENTA}{file_format_ext}{style.RESET}){style.RESET} ---"
    )
    if not set_download_parameters(driver, download_type, year, month, file_format_ext):
        _log_error(f"Failed to set parameters for {month:02d}/{year}. Skipping.")
        return False

    time.sleep(1)

    captured_url = click_and_capture_url(driver, year, month, file_format_ext)
    if not captured_url:
        _log_error(f"Failed to capture download URL for {month:02d}/{year}. Skipping.")
        return False

    if download_data_with_correction(
        captured_url,
        year,
        month,
        file_format_ext,
        download_dir,
    ):
        _log_success(
            f"Successfully processed and downloaded data for {month:02d}/{year}.",
        )
        return True
    else:
        _log_error(f"Failed to download data for {month:02d}/{year}.")
        return False


def download_cen_files_batch(
    dates_to_download,
    download_type_setting,
    file_format_setting,
    base_save_path=".",
):
    _log_info(f"{style.BOLD}Initializing batch download process...{style.RESET}")
    driver, actual_download_dir = initialize_driver_and_navigate(base_save_path)

    if not driver:
        _log_error("Failed to initialize WebDriver. Aborting batch process.")
        return

    overall_success_count = 0
    try:
        for i, (year, month) in enumerate(dates_to_download):
            if i > 0:
                _log_info("Pausing briefly before processing next date...")
                time.sleep(3)

            success = download_single_cen_file(
                driver,
                actual_download_dir,
                download_type_setting,
                year,
                month,
                file_format_setting,
            )
            if success:
                overall_success_count += 1
            else:
                _log_warning(f"Problem occurred processing {month:02d}/{year}.")

    except Exception as e:
        _log_error(
            f"An critical error occurred during batch processing: {type(e).__name__} - {e}",
        )
    finally:
        if driver:
            _log_info("Closing browser...")
            driver.quit()
        summary_color = (
            style.GREEN
            if overall_success_count == len(dates_to_download)
            else style.YELLOW
            if overall_success_count > 0
            else style.RED
        )
        _log_info(
            f"{style.BOLD}Batch download process finished. Successfully downloaded {summary_color}{overall_success_count}/{len(dates_to_download)}{style.RESET} files.{style.RESET}"
        )


if __name__ == "__main__":
    # single_date_list = [(2025, 5)]  # Year, Month
    # download_cen_files_batch(
    #     dates_to_download=single_date_list,
    #     download_type_setting="unidad",
    #     file_format_setting="tsv",
    #     base_save_path=".",  # Save in "downloads" subdirectory of current script location
    # )

    dates_for_batch = [
        (2024, 11),
        (2024, 12),
        (2025, 1),
        (2025, 2),  # Assuming this might fail to show mixed results
    ]
    download_cen_files_batch(
        dates_to_download=dates_for_batch,
        download_type_setting="unidad",
        file_format_setting="tsv",
    )
