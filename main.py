from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import time
import discord, random
from discord import app_commands as ac
from discord.ext.commands import has_permissions, MissingPermissions
import asyncio



BOT_TOKEN = ""
with open("token.txt", "r") as file:
    BOT_TOKEN = file.read()
    
POLL_CHANNEL = None

list_of_movies = []
movie_vote_counts = {}
users_who_voted = []

choose_random = True
currently_voting = False

scheduler = BackgroundScheduler()

vote_message = None


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents, application_id=1343728099833151499)
tree = ac.CommandTree(client)

@client.event
async def on_ready():
    scheduler.add_job(BeginSelection, CronTrigger(day_of_week='fri', hour=22, minute=0), id="BeginSelection")
    scheduler.start()

    for guild in client.guilds:
        await guild.system_channel.send("Successfully activated!")

    await tree.sync()

@tree.command(
    name="setchannel",
    description="Admin command - Sets the channel for the poll."
)
@has_permissions(administrator=True) 
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    global POLL_CHANNEL
    POLL_CHANNEL = channel
    await interaction.response.send_message("Successfully set " + channel.name + " to the movie night poll channel.")

@setchannel.error
async def setchannel_error(interaction: discord.Interaction, error: Exception):
   if isinstance(error, MissingPermissions):
       await interaction.response.send_message("You don't have permission to do change the poll channel!", ephemeral=True)

@tree.command(
    name="nominate",
    description="Nominate a movie."
)
async def nominate(interaction: discord.Interaction, movie_name: str):
    if not currently_voting:
        await AddMovieToList(movie_name, interaction)
    else:
        await interaction.response.send_message("You cannot add more movies during the voting process!", ephemeral=True)

@tree.command(
    name="vote",
    description="Vote from the list of movies."
)
async def vote(interaction: discord.Interaction, movie_id: int):
    if interaction.user not in users_who_voted:
        if movie_id <= len(list_of_movies) and movie_id > 0:
            if movie_id - 1 in movie_vote_counts:
                movie_vote_counts[movie_id - 1] += 1
            else:
                movie_vote_counts[movie_id - 1] = 1

            users_who_voted.append(interaction.user)
            await UpdateVoteCount()
            await interaction.response.send_message("Successfully voted for **" + str(movie_id) + " - " + list_of_movies[movie_id - 1][0] + "**!")
        else:
            await interaction.response.send_message("That is an invalid movie ID.", ephemeral=True)
    else:
        await interaction.response.send_message("You have already voted!", ephemeral=True)


@tree.command(
    name="nominations",
    description="Shows the current list of movie nominations and their IDs."
)
async def nominations(interaction: discord.Interaction):
    await PrintNominations(interaction)

@tree.command(
    name="togglerandom",
    description="Admin command - Toggles random movie selection or voting on/off. Default value is ON."
)
@has_permissions(administrator=True) 
async def togglerandom(interaction: discord.Interaction):
    global choose_random
    if not currently_voting:
        if choose_random:
            choose_random = False
            await interaction.response.send_message("Successfully toggled random selection **OFF**.")

        else:
            choose_random = True
            await interaction.response.send_message("Successfully toggled random selection **ON**.")
    else:
        await interaction.response.send_message("You cannot toggle on/off the random selection during the voting process!", ephemeral=True)

@togglerandom.error
async def togglerandom_error(interaction: discord.Interaction, error: Exception):
    if isinstance(error, MissingPermissions):
        await interaction.response.send_message("You do not have perrmission to toggle on/off the random selection!", ephemeral=True)

@tree.command(
    name="unnominate",
    description="Unnominates the selected movie ID from the list."
)
async def unnominate(interaction: discord.Interaction, movie_id: int):
    if not currently_voting:
        await RemoveMovieFromList(movie_id, interaction, interaction.user.guild_permissions.administrator)
    else:
        await interaction.response.send_message("You cannot remove a movie during the voting process!", ephemeral=True)

@tree.command(
    name="forceselection",
    description="Admin command - Force the selection process (either voting or random selection) to begin."
)
@has_permissions(administrator=True) 
async def forceselection(interaction: discord.Interaction):
    await BeginSelection()
    await interaction.response.send_message("Forcing the selection process to begin.")


@forceselection.error
async def forceselection_error(interaction: discord.Interaction, error: Exception):
    if isinstance(error, MissingPermissions):
        await interaction.response.send_message("You do not have permission to force a movie selection!", ephemeral=True)

@tree.command(
    name="forceendvote",
    description="Admin command - Force the voting process to end immediately."
)
@has_permissions(administrator=True) 
async def forceendvote(interaction: discord.Interaction):
    if currently_voting:
        await interaction.response.send_message("Forcing the vote to end.")
        await EndPoll()
    else:
        await interaction.response.send_message("There is no active movie night poll.", ephemeral=True)

@forceselection.error
async def forceselection_error(interaction: discord.Interaction, error: Exception):
    if isinstance(error, MissingPermissions):
        await interaction.response.send_message("You do not have permission to force the vote to end!", ephemeral=True)

#
#
#
#
#### Helper Functions ####
#
#
#
#

async def AddMovieToList(movieName: str, interaction: discord.Interaction):
    user = interaction.user
    id = len(list_of_movies)
    list_of_movies.append((movieName, user))

    await interaction.response.send_message("Successfully nominated " + movieName + " for movie night!")
    


async def RemoveMovieFromList(movieID: int, interaction: discord.Interaction, isAdmin: bool):
    user = interaction.user

    for id, (movie, user2) in enumerate(list_of_movies):
        if movieID == id + 1:
            if user.id == user2.id or isAdmin:
                list_of_movies.pop(id)
                await interaction.response.send_message("Successfully removed " + movie + " from the list of nominations.")
                return
            
            else:
                await interaction.response.send_message("You do not have permission to remove others' nominations!", ephemeral=True)
                return
            
    await interaction.response.send_message("The specified movie ID was not found.", ephemeral=True)

async def PrintNominations(interaction: discord.Interaction):
    if list_of_movies:
        embed = discord.Embed(
            title="🍿 Movie Nominations",
            description="To remove a nomination, do /unnominate <id> (Must the user who nominated the movie or have administrator permissions)",
            color=discord.Color.blue()
        )

        for id, (movie, user) in enumerate(list_of_movies):
            embed.add_field(name=str(id + 1) + ": " + movie, value="Nominated by " + f"<@{user.id}>", inline=False)
        
        await interaction.response.send_message(embed=embed)
        
    else:
        await interaction.response.send_message("There are no movies in the nominations list!")

async def PrintVotingNominations():
    global vote_message
    if list_of_movies:
        embed = discord.Embed(
        title="🍿 It's Time To Vote!",
        description="Use /vote <id> to vote for the movie you wish to watch. Voting concludes on Saturday at 5:00 PM.",
        color=discord.Color.blue()
    )
        for id, (movie, user) in enumerate(list_of_movies):
            embed.add_field(name=str(id + 1) + ": " + movie, value="Votes: 0 - Nominated by " + f"<@{user.id}>", inline=False)
        
        vote_message = await POLL_CHANNEL.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
    else:
        await POLL_CHANNEL.send("Uh oh... there were no nominations for movie night this week...")

async def UpdateVoteCount():
    global vote_message
    updated_embed = discord.Embed(
        title = vote_message.embeds[0].title,
        description = vote_message.embeds[0].description,
    )

    for id, (movie, user) in enumerate(list_of_movies):
            if id in movie_vote_counts:
                updated_embed.add_field(name=str(id + 1) + ": " + movie, value="Votes: " + str(movie_vote_counts[id]) + " - Nominated by " + f"<@{user.id}>", inline=False)
            else:
                movie_vote_counts[id] = 1
                updated_embed.add_field(name=str(id + 1) + ": " + movie, value="Votes: " + str(movie_vote_counts[id]) + " - Nominated by " + f"<@{user.id}>", inline=False)

    if isinstance(vote_message, discord.Message):
        await vote_message.edit(embed=updated_embed)

async def PrintRandomChoice():
    if list_of_movies:
        chosen_movie_id = random.randint(1, len(list_of_movies))
        chosen_movie = list_of_movies[chosen_movie_id - 1]
        list_of_movies.pop(chosen_movie_id - 1)

        embed = discord.Embed(
            title = chosen_movie[0],
            description = "Nominated by " + f"<@{chosen_movie[1].id}>"
        )
        await POLL_CHANNEL.send("🍿 It's almost Movie Night! Tonight's movie is: ", embed=embed, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
    else:
        await POLL_CHANNEL.send("Uh oh... there were no nominations for movie night this week...")


async def BeginSelection():
    global currently_voting
    if choose_random:
        await PrintRandomChoice()
    else:
        await InitPoll()
        print("Successfully init poll")
        currently_voting = True
        await PrintVotingNominations()
        print("Successfully print voting nominations")


async def InitPoll():
    scheduler.add_job(lambda: asyncio.create_task(EndPoll()), CronTrigger(day_of_week='sat', hour=15, minute=0), id="ClosePoll")
    print("Added scheduler job")
    movie_vote_counts.clear()
    for id, (movie, user) in enumerate(list_of_movies):
        movie_vote_counts[id] = 0
    print("Enumerated on movies")

async def EndPoll():
    global currently_voting
    scheduler.remove_job("ClosePoll")
    currently_voting = False
    chosen_movie_id = -1
    chosen_movie_vote_count = -1
    tied_movies = []
    for movie_id, vote_count in movie_vote_counts.items():
        if vote_count > chosen_movie_vote_count:
            chosen_movie_id = movie_id
            chosen_movie_vote_count = vote_count
            tied_movies.clear()
        elif vote_count == chosen_movie_vote_count:
            tied_movies.append(movie_id)

    if tied_movies:
        tied_movies.append(chosen_movie_id)
        chosen_movie_id = tied_movies[random.randint(0, len(tied_movies) - 1)]
        

    chosen_movie = list_of_movies[chosen_movie_id - 1]
    list_of_movies.pop(chosen_movie_id - 1)
    embed = discord.Embed(
            title = chosen_movie[0],
            description = "Nominated by " + f"<@{chosen_movie[1].id}>"
        )
    embed.set_footer(text="Won with " + str(movie_vote_counts[chosen_movie_id]) + " votes")
    await POLL_CHANNEL.send("🍿 It's almost Movie Night! Tonight's movie is: ", embed=embed, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

client.run(BOT_TOKEN)

