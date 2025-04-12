from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def search_bulgarian_company(company_name):
    """
    Search for a company in the Bulgarian Registry Agency portal.
    
    Args:
        company_name (str): The name of the company to search for.
        
    Returns:
        tuple: (search_url, success) if found, (None, False) otherwise.
    """
    logger.info(f"Searching for Bulgarian company: {company_name}")
    
    try:
        # Initialize undetected-chromedriver with specific version
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        options.add_argument('--disable-site-isolation-trials')
        
        driver = uc.Chrome(options=options, version_main=134)
        logger.info("Chrome driver initialized successfully")
        
        # Set page load timeout
        driver.set_page_load_timeout(30)
        
        # Construct the direct search URL with the correct parameters
        # URL encode the company name
        encoded_company_name = requests.utils.quote(company_name)
        search_url = f"https://portal.registryagency.bg/CR/Reports/VerificationPersonOrg?count=2&includeHistory=false&name={encoded_company_name}&page=1&pageSize=25&selectedSearchFilter=1"
        
        # Navigate directly to the search results page
        driver.get(search_url)
        logger.info(f"Navigated directly to search URL: {search_url}")
        
        # Wait for the page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        logger.info("Page loaded successfully")
        
        # Take a screenshot for debugging
        driver.save_screenshot("search_results_screenshot.png")
        logger.info("Saved screenshot for debugging")
        
        # Get the current URL after search
        final_url = driver.current_url
        logger.info(f"Final URL: {final_url}")
        
        # Check if we're on a results page
        if "VerificationPersonOrg" in final_url:
            logger.info("Successfully loaded search results page")
            driver.quit()
            return final_url, True
        else:
            logger.error("Failed to load search results page")
            driver.quit()
            return None, False
        
    except TimeoutException as e:
        logger.error(f"Timeout error: {str(e)}")
        return None, False
    except NoSuchElementException as e:
        logger.error(f"Element not found: {str(e)}")
        return None, False
    except Exception as e:
        logger.error(f"Error searching for Bulgarian company: {str(e)}")
        return None, False
    finally:
        try:
            if 'driver' in locals():
                driver.quit()
        except Exception as e:
            logger.error(f"Error closing driver: {str(e)}")

def search_ft_company(company_name):
    try:
        # Format the company name for the search URL - try different variations
        search_variations = [
            company_name,
            company_name.replace('Corporation', 'Corp'),
            company_name.replace('Corp', 'Corporation')
        ]
        
        for search_query in search_variations:
            # Format the search query
            search_query = search_query.strip().replace(' ', '+')
            search_url = f"https://markets.ft.com/data/search?query={search_query}"
            
            # Make a request to the search page
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the first equity result
            equity_link = soup.find('a', href=re.compile(r'/data/equities/tearsheet/summary\?s='))
            
            if equity_link:
                ft_link = f"https://markets.ft.com{equity_link['href']}"
                print(f"Found FT link: {ft_link}")  # Debug log
                
                # Get the company details page
                response = requests.get(ft_link, headers=headers)
                details_soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all divs with the data table class
                key_stats_divs = details_soup.find_all('div', class_='mod-tearsheet-key-stats__data__table')
                print(f"Found {len(key_stats_divs)} data table divs")  # Debug log
                
                shares_outstanding = None
                free_float = None
                
                # Look for the div that also has the extra class
                for div in key_stats_divs:
                    if 'mod-tearsheet-key-stats__extra' in div.get('class', []):
                        print("Found key stats extra div")  # Debug log
                        table = div.find('table')
                        if table:
                            print("Found table in extra div")  # Debug log
                            rows = table.find_all('tr')
                            print(f"Processing table with {len(rows)} rows")  # Debug log
                            
                            for row in rows:
                                th = row.find('th')
                                td = row.find('td')
                                if th and td:
                                    # Get the text without any sub-elements
                                    label = th.get_text(strip=True, separator=' ').lower()
                                    value = td.get_text(strip=True, separator=' ').split()[0]  # Get first part of value
                                    print(f"Found row - Label: '{label}', Value: '{value}'")  # Debug log
                                    
                                    if label == 'shares outstanding':
                                        try:
                                            value = value.lower()
                                            if value == '--':
                                                continue
                                            if 'bn' in value:
                                                shares_outstanding = float(value.replace('bn', '').replace(',', '')) * 1000
                                            elif 'b' in value:
                                                shares_outstanding = float(value.replace('b', '').replace(',', '')) * 1000
                                            elif 'm' in value:
                                                shares_outstanding = float(value.replace('m', '').replace(',', ''))
                                            print(f"Found shares outstanding: {shares_outstanding}")  # Debug log
                                        except ValueError as e:
                                            print(f"Error parsing shares outstanding value: {e}")  # Debug log
                                            continue
                                    elif label == 'free float':
                                        try:
                                            value = value.lower()
                                            if value == '--':
                                                continue
                                            if 'bn' in value:
                                                free_float = float(value.replace('bn', '').replace(',', '')) * 1000
                                            elif 'b' in value:
                                                free_float = float(value.replace('b', '').replace(',', '')) * 1000
                                            elif 'm' in value:
                                                free_float = float(value.replace('m', '').replace(',', ''))
                                            print(f"Found free float: {free_float}")  # Debug log
                                        except ValueError as e:
                                            print(f"Error parsing free float value: {e}")  # Debug log
                                            continue
                
                # Calculate free float percentage if we have both values
                if shares_outstanding and free_float and shares_outstanding > 0:
                    free_float_percentage = (free_float / shares_outstanding) * 100
                    print(f"Calculated free float percentage: {free_float_percentage}%")  # Debug log
                    return {
                        'success': True,
                        'ft_link': ft_link,
                        'free_float_percentage': round(free_float_percentage, 2),
                        'message': f'The company is publicly traded with the free float of {round(free_float_percentage, 2)}%, the source link: {ft_link}'
                    }
                
                print("Could not find both shares outstanding and free float values")  # Debug log
                return {
                    'success': True,
                    'ft_link': ft_link,
                    'free_float_percentage': None,
                    'message': f'The company is publicly traded. You can find more information at: {ft_link}'
                }
        
        print("No equity link found")  # Debug log
        return {
            'success': False,
            'message': 'The company is not found as a publicly traded company on Financial Times.',
            'ft_link': None,
            'free_float_percentage': None
        }
    except Exception as e:
        print(f"Error in search_ft_company: {str(e)}")  # Debug logging
        return {
            'success': False,
            'message': f"Sorry, there was an error checking the company. Please try again.",
            'ft_link': None,
            'free_float_percentage': None
        }

def validate_uic(uic):
    """
    Validate a Bulgarian UIC (Unique Identification Code).
    
    Args:
        uic (str): The UIC to validate.
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check if the input is numeric
    if not uic.isdigit():
        return False, "Invalid UIC: Must contain only numbers"
    
    # Check if the length is between 9 and 13 digits
    if not (9 <= len(uic) <= 13):
        return False, "Invalid UIC: Must be between 9 and 13 digits"
    
    return True, None

def generate_uic_url(uic):
    """
    Generate the direct company status result URL for a given UIC.
    
    Args:
        uic (str): The validated UIC.
        
    Returns:
        str: The direct URL to the company's status page.
    """
    return f"https://portal.registryagency.bg/CR/Reports/ActiveConditionTabResult?uic={uic}"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/check_company', methods=['POST'])
def check_company():
    data = request.json
    company_name = data.get('company_name', '').strip()
    uic = data.get('uic', '').strip()
    
    # Handle UIC-based search
    if uic:
        logger.info(f"Received request to check UIC: {uic}")
        
        # Validate the UIC
        is_valid, error_message = validate_uic(uic)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': error_message
            })
        
        # Generate the direct URL
        result_url = generate_uic_url(uic)
        
        return jsonify({
            'success': True,
            'message': f"Here is the direct link to the company's status page:",
            'search_url': result_url,
            'details_url': result_url
        })
    
    # Handle company name-based search (existing functionality)
    if not company_name:
        return jsonify({
            'success': False,
            'message': 'Please provide either a company name or UIC'
        })
    
    logger.info(f"Received request to check company: {company_name}")
    
    # Check if the company name contains Cyrillic characters
    if re.search('[\u0400-\u04FF]', company_name):
        logger.info("Company name contains Cyrillic characters, using Bulgarian Registry Agency search")
        
        # Search in Bulgarian Registry Agency
        search_url, success = search_bulgarian_company(company_name)
        
        if success and search_url:
            return jsonify({
                'success': True,
                'message': f"Search completed for '{company_name}'. Click the link below to view the results:",
                'search_url': search_url,
                'uic': None,  # We don't extract UIC in this version
                'details_url': search_url
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Sorry, we couldn't find information about '{company_name}' in the Bulgarian Registry Agency. The search may have timed out or the company may not be registered. Please try again later or check the company name."
            })
    else:
        # Use the existing FT search for non-Cyrillic company names
        result = search_ft_company(company_name)
        return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5001) 