import pickle
import os
import sys
import base64
from time import sleep
from cryptography.fernet import Fernet
from datetime import datetime, date
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

# pyinstaller --onefile -w 'main.py'

expiration_date = date(2029, 9, 2)
if sys.argv[0][-3:] == ".py":
    key = Fernet.generate_key()
    encrypt = Fernet(key)
    enc_allowed_users = base64.b64encode(
        encrypt.encrypt("username1;username2;username3".encode())) # only username1@berkeley.edu, username2@berkeley.edu, username3@berkeley.edu are allowed to use this program
    print("Key: ", base64.b64encode(key), " Users: ", enc_allowed_users)
else:
    key = base64.b64decode('KEY') # key to access encrypted string of authorized users
    enc_allowed_users = 'ENCRYPTED_STRING' # encrypted string of authorized users
    encrypt = Fernet(key)

decoded_user_names = encrypt.decrypt(
    base64.b64decode(enc_allowed_users)).decode()
cookie_file_name = "cookie.pkl"
allowed_users = decoded_user_names.split(";")

def open_browser():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1080,1080")
    return Chrome(
        os.path.dirname(sys.argv[0]) + "/chromedriver",
        options=chrome_options)

def login_with_cookies(driver: Chrome):
    has_cookie = os.path.isfile(cookie_file_name)
    if has_cookie:
        driver.get('https://auth.berkeley.edu/')
        cookies = pickle.load(open(cookie_file_name, "rb"))
        for cookie in cookies:
            driver.add_cookie(cookie)
    
    return just_login(driver)

def just_login(driver: Chrome):
    driver.get('https://shop.rs.berkeley.edu/booking/')
    driver.execute_script(
        "javascript:showLogin('/booking/');",
        driver.find_elements_by_id("loginLink-mobile")[0])
    driver.implicitly_wait(3)
    driver.find_element_by_css_selector("[title='CalNet Login']").click()
    driver.implicitly_wait(3)

    if "auth.berkeley.edu" in driver.current_url:
        print("Please login on the browser...")

        username = ''
        while "auth.berkeley.edu" in driver.current_url:
            try:
                new_username = driver.find_element_by_id("username").get_attribute('value')
                if username != new_username:
                    username = new_username
            except StaleElementReferenceException:
                sleep(0.1)
            except NoSuchElementException:
                # user may have already signed in, so let's ignore this
                sleep(0.1)
        
        if allowed_users.count(username.lower()) == 0:
            return False

    return True

def check_logged_in(driver: Chrome):
    driver.get('https://shop.rs.berkeley.edu/booking/')
    return len(driver.find_elements_by_id("loginLink-mobile")) == 0

def update_cookie_jar(driver: Chrome):
    # now update the cookie jar
    # driver.get('https://auth.berkeley.edu/')
    # pickle.dump( driver.get_cookies() , open(cookie_file_name,"wb"))

    # driver.get('https://shop.rs.berkeley.edu/booking/')

    driver.implicitly_wait(1)
    if len(driver.find_elements_by_id("gdpr-cookie-accept")) > 0:
        driver.find_element_by_id("gdpr-cookie-accept").click()

def wait_for_element(driver: Chrome, css_selector: str):
    while True:
        elements = driver.find_elements_by_css_selector(css_selector)
        if len(elements) > 0:
            return elements
        sleep(1)

def open_last_day(driver: Chrome):
    driver.implicitly_wait(2)
    dayButtons = wait_for_element(driver, ".btn.single-date-select-button.single-date-select-one-click")
    dayButtons[-1].click()
    driver.implicitly_wait(1)

def book_appointment(driver: Chrome):
    # loop by navigating to home so that session does not log out.
    driver.get('https://shop.rs.berkeley.edu/booking/')
    bookingPageUrl = wait_for_element(driver, ".inherit-link")[1].get_attribute("href")

    # now click on bookings link
    for _ in range(0, 32):
        # navigate / refresh the bookings page.
        driver.get(bookingPageUrl) 
        driver.implicitly_wait(0.5)
        open_last_day(driver)

        # for time being use temp test page for the process, this should let us test clicking on booking button.
        # driver.get('file:///D:/Users/nisha/Downloads/tmp3.html')
        all_btns = wait_for_element(driver, ".booking-slot-item > div > button")
        disabled_btns = driver.find_elements_by_css_selector(".booking-slot-item > div > button.disabled")

        if len(all_btns) > len(disabled_btns):
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", all_btns[len(all_btns) - 1])
            driver.implicitly_wait(2)
            all_btns[len(all_btns) - 1].click()
            driver.implicitly_wait(10)
            return True

    return False

def to_time(reserve_time_text: str):
    reserve_time_text_am = reserve_time_text[-2:] == 'AM'
    reserve_time_text_snippet = reserve_time_text[9:-3]
    if len(reserve_time_text_snippet.split(':')) == 1:
        reserve_time_text_snippet += ":00"

    hour, minute = map(int, reserve_time_text_snippet.split(':'))
    if not reserve_time_text_am:
        hour = hour + 12

    today = date.today()
    return datetime(today.year, today.month, today.day, hour, minute)

def get_wait_time(driver: Chrome, chosen_time: datetime):
    driver.get('https://shop.rs.berkeley.edu/booking/')

    # now navigate to bookings page
    bookingPageUrl = wait_for_element(driver, ".inherit-link")[1].get_attribute("href")
    driver.get(bookingPageUrl)
    driver.implicitly_wait(1)

    # go to the newest date available by clicking on -la-st element of date selection list.
    open_last_day(driver)

    # now get next available appointment time text.
    availableTimes = map(
        lambda elem: to_time(elem.text),
        driver.find_elements_by_class_name("booking-slot-item-right.booking-slot-reserved-item"))
    availableTimes = list(availableTimes)

    reserve_time = availableTimes[0]
    if chosen_time is None:
        for idx in range(len(availableTimes)):
            print("[", idx, "]", availableTimes[idx].time())

        choice = 0
        while True:
            choice = input('Pick time slot (default: 0): ')
            if len(choice) > 0:
                choiceIdx = int(choice)
                if choiceIdx < len(availableTimes):
                    reserve_time = availableTimes[choiceIdx] 
                    break
                else:
                    print('Pick values between 0 & ', len(availableTimes) - 1)
            else:
                break
    else:
        if chosen_time > reserve_time:
            reserve_time = chosen_time

    # compute next available time.
    current_time = datetime.now()
    delta_time = reserve_time - current_time
    return (delta_time.total_seconds(), reserve_time)

def get_wait_time_mini(reserve_time):
    return max(0, (reserve_time - datetime.now()).total_seconds())

driver = open_browser()
is_good_user = login_with_cookies(driver)
if not check_logged_in(driver) and is_good_user:
    if os.path.isfile(cookie_file_name):
        os.remove(cookie_file_name)
    just_login(driver)

if is_good_user:
    update_cookie_jar(driver)

reserve_time = None
while True:
    wait_time, reserve_time = get_wait_time(driver, reserve_time)
    print("Waiting for ", wait_time, " seconds")

    while wait_time > 15:
        sleep(15)
        wait_time = get_wait_time_mini(reserve_time)

    sleep(max(0, wait_time - 5))

    if not check_logged_in(driver):
        just_login(driver)
    
    wait_time = get_wait_time_mini(reserve_time)
    sleep(wait_time)

    if datetime.today().date() < expiration_date and is_good_user and book_appointment(driver):
         sleep(60)
         break
