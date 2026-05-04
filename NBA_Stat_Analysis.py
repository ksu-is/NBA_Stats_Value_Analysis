
import time
from nba_api.stats.static import players
from nba_api.stats.endpoints import CommonPlayerInfo, playercareerstats
from tabulate import tabulate

import re
import numpy as np
import unicodedata

# Imports required for the basketball reference ID generation
from bs4 import BeautifulSoup, Comment
from selenium import webdriver
from selenium.webdriver.chrome.options import Options 
import requests

#Imports for visualization
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import seaborn as sns


print("Welcome to the NBA Statistics Presenter! \nThis program allows you to search for NBA player stats.")

# Function to fetch the full HTML content of a page using Selenium, which can handle dynamic content that may not be present in the initial HTML source
def fetch_full_html_with_selenium(url):
    options = Options()
    options.add_argument("--headless")  # Run in headless mode
    driver = webdriver.Chrome(options=options)  # Adjust if chromedriver is in a different location

    driver.get(url)
    full_html = driver.page_source
    driver.quit()
    return full_html

# Function to find a table in the comments of the HTML, since some tables on basketball reference are loaded in comments and not directly in the HTML
def find_table_in_comments(soup, table_id):
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment_soup = BeautifulSoup(comment, "html.parser")
        table = comment_soup.find("table", {"id": table_id})
        if table:
            return table
    return None

# Gets Date of birth on basketball reference
def find_bbr_dob(soup):
    birth_span = soup.find("span", {"id": "necro-birth"})
    if birth_span and birth_span.has_attr('data-birth'):
        return birth_span['data-birth']
    return None

# Get Date of Birth from NBA API
def get_nba_api_dob(player_id):
    info = CommonPlayerInfo(player_id=player_id).get_data_frames()[0]
    # The NBA API returns '1992-12-18T00:00:00'
    raw_date = info['BIRTHDATE'].iloc[0] 
    return raw_date.split('T')[0]  # Clean it to '1992-12-18'

# Function to generate the basketball reference ID based on the player's full name, which is necessary to construct the URL for fetching salary data from basketball reference
def generate_basketball_reference_id(full_name):
    name_parts = full_name.split()
    if len(name_parts) < 2:
        raise ValueError("Please enter a full name (first and last).")
    
    first_name = name_parts[0]
    last_name = name_parts[-1]

    cleaned_first_name = clean_name(first_name)
    cleaned_last_name = clean_name(last_name)

    # Create the basketball reference ID format
    first_part = cleaned_last_name[:5].lower()
    second_part = cleaned_first_name[:2].lower()

    basketball_reference_id = f"{first_part}{second_part}"
    return basketball_reference_id

# Function to get the proper url by matching basketball reference DOB and NBA API DOB
def get_correct_bbr_url(full_name, player_id):
    base_id = generate_basketball_reference_id(full_name)
    target_dob = get_nba_api_dob(player_id)
    
    # Try suffixes 01 through 05 (rarely goes higher)
    for i in range(1, 6):
        suffix_id = f"{base_id}{i:02d}"
        url = f"https://www.basketball-reference.com/players/{suffix_id[0]}/{suffix_id}.html"
        
        
        # Checks the url if the 2 Date of births match
        response = requests.get(url)
        if response.status_code == 200:
            temp_soup = BeautifulSoup(response.content, "html.parser")
            scraped_dob = find_bbr_dob(temp_soup)
            
            if scraped_dob == target_dob:
                print(f"Match found! ID: {suffix_id}")
                return url
    
    return None # No match found


# Clean the salary value by removing non-numeric characters and handling special cases like Two-Way contracts and Minimum contracts, which have specific values assigned to them for the purpose of this analysis
def clean_salary(value):
    # Defined values for Two-Way contracts and Minimum contracts based on typical salary figures for those contract types in the NBA. Basketball reference does not provide numeric values for these contract types
    TW_VALUE = 578577
    MINIMUM_VALUE = 1272870
    if value is None:
        return 'N/A'

    value = str(value)

    # Two-Way contract
    if "(TW)" in value or "Two-Way" in value:
        return TW_VALUE

    # Minimum contract
    if "Minimum" in value:
        return MINIMUM_VALUE

    return value 

# Function to remove any non-alphanumeric characters from the player's name and convert it to lowercase
def clean_name(name):
    ## 1. Normalize Unicode characters (converts 'ć' to 'c' + accent)
    normalized = unicodedata.normalize('NFKD', name)
    # 
    ascii_name = "".join([c for c in normalized if not unicodedata.combining(c)])

    cleaned_name = re.sub(r'[^a-zA-Z0-9]', '', ascii_name).lower()
    return cleaned_name

# Function to fetch the career salary data for a player from basketball reference
def career_salary(full_name, player_id):
    url = get_correct_bbr_url(full_name, player_id)
    print(f"Fetching page with Selenium: {url}")

    full_html = fetch_full_html_with_selenium(url)

    soup = BeautifulSoup(full_html, "html.parser")
   
    # Initialize an empty dictionary to store the salary data
    salary_dict = {}

    # Find the salary table by its ID
    table_career = soup.find("table", {"id": "all_salaries"})
    if not table_career:
        # Checks the comments for the table
        table_career = find_table_in_comments(soup, "all_salaries") 
    if not table_career:
        # print("Salary table not found in the loaded page.")
        return salary_dict

    # Extract the table body for the salary data
    tbody_career = table_career.find("tbody")
    if not tbody_career:
        # print("Career Salary table body not found.")
        return salary_dict
    
    # Checks if the player is active before trying to access the contract table, as it only exists for active players
    player_status = players.find_players_by_full_name(full_name)[0]
    if player_status['is_active'] == True:
        print("Player is active, checking for contract salary...")
        # player_id = players.find_players_by_full_name(full_name)[0]['id']
        team_abbreviation = CommonPlayerInfo(player_id=player_id).get_data_frames()[0]['TEAM_ABBREVIATION'][0]
        # print(f"Team Abbreviation: contracts_{team_abbreviation.lower()}")
        table_id = f"contracts_{team_abbreviation.lower()}"
        table_contract = soup.find("table", {"id": table_id})
        # print(f"Looking for contract table with ID: {table_id}")

        # When the contract table is found, look for the table body and header. This step will be skipped if the contract table is not found, which will happen for retired players, and the salary dictionary will only contain the career salary data from the salaries table.
        if table_contract:
            tbody_contract = table_contract.find("tbody")
            table_head = table_contract.find("thead")
            # If both the table body and header are found, extract the seasons from the header and look for the target season in the contract row to get the salary for that season
            if tbody_career and table_head:
                header_cells = table_head.find_all("th")
                # Gets the season column is the second column (index 1)
                seasons = [th.text.strip() for th in header_cells[1:]]
                target_season = "2025-26"
                # Check if the target season is in the list of seasons and if so, find the corresponding salary value from the contract row
                if target_season in seasons:
                    indx = seasons.index(target_season)
                    contract_row = tbody_contract.find("tr")
                    # If the contract row is found, extract the salary value for the target season and add it to the salary dictionary with the season as the key
                    if contract_row:
                        cells = contract_row.find_all("td")[1:]
                        # Check if the index for the target season is within the range of available cells in the contract row before trying to access it
                        if indx < len(cells):
                            contract_cell = cells[indx]
                            contract_value = contract_cell.text.strip()
                            salary_dict[target_season] = contract_value  
                        else:
                            print(f"Season {target_season} not found in contract table.")

    # Extract career salary data into a dictionary with season as key and salary as value
    for row in tbody_career.find_all("tr"):
        season_cell = row.find("th", {"data-stat": "season"})
        salary_cell = row.find("td", {"data-stat": "salary"})
        if season_cell and salary_cell:
            season = season_cell.text.strip()
            salary_value = salary_cell.text.strip()
            cleaned_salary = clean_salary(salary_value)
            salary_dict[season] = cleaned_salary 
    
    return salary_dict

# Initialize the statistic finder function
def player_stats():
    while True:
        # Receive user input for player name
        search = input("Enter the name of a player or 'q' to exit: ").strip().lower()
        if search == "q":
            print("Thank you, exiting the program.")
            return
        elif search == "":
            print("No input provided.")
            continue
       
        print("Searching for player...")
        time.sleep(1.5)  # Simulate a delay for the search

        # Use regex to find players with similar names
        matches = players.find_players_by_full_name(search)
        if not matches:
            print("No players found with that name.")
            continue
        elif len(matches) > 1:
            print("Multiple players found with that name. Please be more specific.")
            for i, match in enumerate(matches):
                print("{}: {}".format(i + 1, match['full_name'])  )
            try:
                choice = int(input("Select a player by number: ")) - 1
                if choice < 0 or choice >= len(matches):
                    print("Invalid choice.")
                    continue
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue
        else:
            choice = 0
       
        # Get the selected player
        selected_player = matches[choice]
        player_id = selected_player['id']
        full_name = selected_player['full_name']

        print("Player found: {}".format(full_name))

        # Get player stats
        career_stats = playercareerstats.PlayerCareerStats(player_id=player_id)
        career_df = career_stats.get_data_frames()[0]

        if career_df.empty:
            print("No career stats available for this player.")
            continue
       
        # Calculations for averages and percentages
        career_df['MPG'] = career_df['MIN'] / career_df['GP']
        career_df['PPG'] = career_df['PTS'] / career_df['GP']
        career_df['APG'] = career_df['AST'] / career_df['GP']
        career_df['RPG'] = career_df['REB'] / career_df['GP']
        career_df['SPG'] = career_df['STL'] / career_df['GP']
        career_df['BPG'] = career_df['BLK'] / career_df['GP']
        career_df['TOV'] = career_df['TOV'] / career_df['GP']
        career_df['FG%'] = (career_df['FG_PCT']*100)
        career_df['FT%'] = (career_df['FT_PCT']*100)
        career_df['3P%'] = (career_df['FG3_PCT']*100)
       
        # Calculate True Shooting Percentage (TS%)
        career_df['TS%'] = career_df['PTS'] / (2 * (career_df['FGA'] + 0.44 * career_df['FTA']))
        career_df['TS%'] = (career_df['TS%'] * 100)
       
        # Calculations for Field Goals Missed and Free Throws Missed
        FGMissed = career_df['FGA'] - career_df['FGM']
        FTMissed = career_df['FTA'] - career_df['FTM']

        # Formula for Credit Score: (PPG + APG + RPG + SPG + BPG) - (TOV + FG Missed + FT Missed)
        credits = (career_df['PPG'] + career_df['APG'] + career_df['RPG'] + career_df['SPG'] + career_df['BPG']) - (career_df['TOV'] + FGMissed + FTMissed)

        # Get salary for the player and map it to the career DataFrame
        salary_data = career_salary(full_name, player_id)
        career_df['SL'] = career_df['SEASON_ID'].map(salary_data)

        # Convert the salary column to a numeric format by removing any non-numeric characters and converting to float
        career_df['Salary_float'] = (career_df['SL'].astype(str).str.replace(r'[^\d]', '', regex=True)) 
        career_df['Salary_float'] = career_df['Salary_float'].replace('', None)
        career_df['Salary_float'] = career_df['Salary_float'].astype(float)
        
        # Formula for Approximate Value (AV): (Credit Score^(3/4))/21
        AV = (abs(credits) ** (3/4)) / 21
        career_df['AV'] = AV
        
        #Calculate the average AV for the player's career and add it as a new column to track Career Effciency (Requires at least 3 season to calculate)
        career_df['CE'] = career_df['AV'].rolling(2).mean()

        # Calculate VD ONLY where salary is greater than 0
        # This avoids the ZeroDivisionError and keeps missing data as NaN
        career_df['VD'] = np.nan
        mask = (career_df['Salary_float'] > 0) & (career_df['Salary_float'].notna())
        career_df.loc[mask, 'VD'] = (career_df['AV'] / (career_df['Salary_float'] / 1000000))  # converts VD to millions for comparison
        
        # Round the stats to one decimal place
        career_df[['MPG','PPG', 'APG', 'RPG', 'SPG', 'BPG', 'TOV','FG%','FT%','3P%','TS%', 'AV']] = career_df[['MPG','PPG', 'APG', 'RPG', 'SPG', 'BPG', 'TOV','FG%','FT%','3P%','TS%', 'AV']].round(1)

        # Map team column to team names
        career_df['Team'] = career_df['TEAM_ABBREVIATION']

        # Loop through each season and replace 'TOT' with the actual team names
        for season in career_df['SEASON_ID'].unique():
            season_rows = career_df[career_df['SEASON_ID'] == season]
            if 'TOT' in season_rows['TEAM_ABBREVIATION'].values:
                teams_played = season_rows[season_rows['TEAM_ABBREVIATION'] != 'TOT']['TEAM_ABBREVIATION'].unique()
                career_df.loc[(career_df['SEASON_ID'] == season) & (career_df['TEAM_ABBREVIATION'] == 'TOT'), 'Team'] = '/'.join(teams_played)

        # Filter the DataFrame to include only the relevant columns ()
        season_stats = career_df[['SEASON_ID','Team' ,'GP','MPG','PPG', 'APG', 'RPG', 'SPG', 'BPG', 'TOV','FG%','FT%','3P%','TS%', 'AV', 'CE', 'SL', 'VD']].copy()
       
        # Rename SEASON_ID column for clarity
        season_stats.rename(columns={'SEASON_ID': 'Season'}, inplace=True)

        #Convert salary from millions for better visualization
        career_df['Salary_M'] = career_df['Salary_float'] / 1e6

        ### Visualization of the stats using matplotlib ###
        x = career_df['Salary_M']
        y = career_df['AV']
        for i, season in enumerate(career_df['SEASON_ID']):
            txt = plt.text(x.iloc[i], y.iloc[i], season[-2:],  # shows only "21", "22", etc.
            fontsize=8, fontweight = 'bold', ha = 'center' # Bolds and centers the Years
            )
            txt.set_path_effects([path_effects.withStroke(linewidth=2, foreground='white')])
        # Scatter plot labels
        plt.xlabel('Salary (Millions USD)')
        plt.ylabel('Approximate Value (AV)')
        plt.title(f'AV vs Salary for {full_name}')
        # Grid Lines
        plt.minorticks_on()
        # Stronger lines for major intervals
        plt.grid(which='major', linestyle='-', linewidth='0.5', color='black', alpha=0.5)
        # Thinner lines for the spaces in between
        plt.grid(which='minor', linestyle=':', linewidth='0.5', color='black', alpha=0.3)
        # Scatter plot
        plt.scatter(x, y, c=range(len(career_df)), cmap='tab20', s=100)
        # plt.colorbar(label='Career Progression')
        # Adds Average AV to the Scatter plot
        avg_av = career_df['AV'].mean()
        plt.axhline(avg_av, color='red', linestyle=':', label=f'Avg AV ({avg_av:.1f})')
        # Regression Line
        z = np.polyfit(x.dropna(), y.dropna(), 1) # degree 1 = linear
        m, b = z  # slope and intercept
        p = np.poly1d(z)
        plt.plot(x, p(x), linestyle='--')
        equation = f"y = {m:.2f}x + {b:.2f}"
        plt.text(0.05, 0.95, equation, transform=plt.gca().transAxes, fontsize=10, verticalalignment='top'
        )

        #heatmap of the stats 
        heatmap_df = career_df[['SEASON_ID', 'AV', 'Salary_float', 'VD']].copy()
        heatmap_df = heatmap_df.set_index('SEASON_ID')
        #Checks if there is a valid Salary to compare
        if career_df['Salary_float'].notna().any():
            # Only standardizes the data if we have variance (std > 0)
            if heatmap_df.std().sum() > 0:
                heatmap_df = (heatmap_df - heatmap_df.mean()) / heatmap_df.std()  # Standardize the data for better visualization in the heatmap
                plt.figure(figsize=(6, 4))
                # Heatmap Colors
                sns.heatmap(heatmap_df, cmap='magma',annot=True)
                #H Heatmap Lables
                plt.title(f'Contract Efficiency Heatmap - {full_name}')
                plt.xlabel('Metric')
                plt.ylabel('Season')
        else:
            print(f":\n[NOTE] Skipping heatmap: No salary data available for {full_name}'s era")


        #Prompt the user to select a season or view all seasons
        while True:
            display_df = season_stats  # season_stats is already the full filtered DataFrame
            if heatmap_df.std().sum() > 0:
                view_choice = input("Would you like to see a heatmap regarding Contract Efficiency & a scatter plot comparing Approxiamate Value and Salary(y/n): ").strip().lower()
                if view_choice == "y":
                    plt.show()
                    break
                elif view_choice =='n':
                    break
                else:
                    print("Invalid input, try again.")
            break


        # Format the season column to be more readable
        print("Career Stats for", full_name) 
        print(tabulate(display_df, headers="keys", tablefmt="pipe", showindex=False))
        # Add a legend for the stats
        print("Legend:\nGP - Games Played \nMPG - Minutes Per Game \nPPG - Points Per Game \nAPG - Assists Per Game \nRPG - Rebounds Per Game \nSPG - Steals Per Game \nBPG - Blocks Per Game \nTOV - Turnovers \nFG% - Field Goal Percentage \nFT% - Free Throw Percentage \n3P% - Three Point Percentage \nTS% - True Shooting Percentage\nAV - Approximate Value \nCE - Career Efficiency \nSL - Salary \nVD - Value over Dollar (AV per million dollars of salary)")
       
# Run the program        
if __name__ == "__main__":
    player_stats()














       
       



