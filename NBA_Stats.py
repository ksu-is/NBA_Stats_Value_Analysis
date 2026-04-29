import time


from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats

from tabulate import tabulate

# Imports required for the basketball reference ID generation
import requests
from bs4 import BeautifulSoup
import pandas as pd 


print("Welcome to the NBA Statistics Presenter! \nThis program allows you to search for NBA player stats.")



def get_salary_for_player(full_name):
    url = f"https://hoopshype.com/salaries/players/"
    
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    players = []
    
    # Find all rows in the salary table
    rows = soup.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) > 1:
            name = cols[1].text.strip()
            salary = cols[2].text.strip()

            players.append((name, salary))

    # Convert to DataFrame
    df = pd.DataFrame(players, columns=["Name", "Salary"])

    # Match player
    match = df[df["Name"].str.lower() == full_name.lower()]

    if not match.empty:
        return match.iloc[0]["Salary"]
    
    return None


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
                print("{}: {}".format(i + 1, match['full_name']))
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

        # Get salary for the player
        salary_value = get_salary_for_player(full_name)
        if salary_value is not None:
            career_df['SL'] = salary_value
        else:
            career_df['SL'] = 'N/A'

        # Formula for Approximate Value (AV): (Credit Score^(3/4))/21
        AV = (abs(credits) ** (3/4)) / 21
        career_df['AV'] = AV

        # Round the stats to one decimal place
        career_df[['MPG','PPG', 'APG', 'RPG', 'SPG', 'BPG', 'TOV','FG%','FT%','3P%','TS%', 'AV']] = career_df[['MPG','PPG', 'APG', 'RPG', 'SPG', 'BPG', 'TOV','FG%','FT%','3P%','TS%', 'AV']].round(1)
         
        # Map team columm to team names
        career_df['Team'] = career_df['TEAM_ABBREVIATION']

        # Loop through each season and replace 'TOT' with the actual team names
        for season in career_df['SEASON_ID'].unique():
            season_rows = career_df[career_df['SEASON_ID'] == season]
            if 'TOT' in season_rows['TEAM_ABBREVIATION'].values:
                teams_played = season_rows[season_rows['TEAM_ABBREVIATION'] != 'TOT']['TEAM_ABBREVIATION'].unique()
                career_df.loc[(career_df['SEASON_ID'] == season) & (career_df['TEAM_ABBREVIATION'] == 'TOT'), 'Team'] = '/'.join(teams_played)

        # Filter the DataFrame to include only the relevant columns
        season_stats = career_df[['SEASON_ID','Team' ,'GP','MPG','PPG', 'APG', 'RPG', 'SPG', 'BPG', 'TOV','FG%','FT%','3P%','TS%', 'AV', 'SL']].copy()
       
        # Rename SEASON_ID column for clarity
        season_stats.rename(columns={'SEASON_ID': 'Season'}, inplace=True)

        #Prompt the user to select a season or view all seasons
        while True:
            view_choice = input("View 'career' stats or 'season' stats? (Enter 'career' or 'season'): ").strip().lower()
            if view_choice == 'career':
                # Use full career_df as before
                display_df = season_stats  # season_stats is already the full filtered DataFrame
                break
            elif view_choice == 'season':
                season_input = input("Enter the season (e.g., '2022-23'): ").strip()
                # Validate and filter to the specific season
                if season_input in career_df['SEASON_ID'].values:
                    display_df = season_stats[season_stats['Season'] == season_input]
                    if display_df.empty:
                        print("No stats found for that season. Try again.")
                        continue
                    break
                else:
                    print("Invalid season or no data for this player in that season. Available seasons: {}".format(', '.join(career_df['SEASON_ID'].unique())))
                    continue
            else:
                print("Invalid choice. Please enter 'career' or 'season'.")
                continue

        # Format the season column to be more readable
        print("Career Stats for", full_name) if view_choice == 'career' else print("Season Stats for", full_name)
        print(tabulate(display_df, headers="keys", tablefmt="pipe", showindex=False))
       
        # Add a legend for the stats
        print("Legend:\nGP - Games Played \nMPG - Minutes Per Game \nPPG - Points Per Game \nAPG - Assists Per Game \nRPG - Rebounds Per Game \nSPG - Steals Per Game \nBPG - Blocks Per Game \nTOV - Turnovers \nFG% - Field Goal Percentage \nFT% - Free Throw Percentage \n3P% - Three Point Percentage \nTS% - True Shooting Percentage\nAV - Approximate Value \nSL - Salary")
       
# Run the program        
if __name__ == "__main__":
    player_stats() 














       
       



