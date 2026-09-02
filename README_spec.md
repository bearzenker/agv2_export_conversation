# Decision Export
We are using the Google Antigravity V2 coding platform. Our goal is create a Python utility that will export a Mark Down README file representing agent activity for a user request. The README will be committed with the code to provide an auditable record of change management decisions. For this exercise, you will be given a path to a test data set, but the code will need to allow this path to be a variable.

You may use free open source Pip installed Python modules to support the export utility. A vitual environment has been intialized: `~/antigravity/agv2_sprint2readme`

## Antigravity V2 Knowledge
The Antigravity V2 utility orchestrates calls to the Gemini agent to perform coding tasks. The utility maintains a knowledge base of activities. The knowledge base is organized by "Projects" and "Conversations". The user attaches the project tier to a code base, likly a Git repo. Inside the project, the user tasks the agent thru conversations.

The conversation has several parts. It begins with the user prompt that tasks the agent. The agent performs "reasoning": background thinking in support of the task. The agent generates TODO lists and/or an implementation plan. As the agent performs the task, they perform additional reasoning. At task completion, the agent ourtputs a response.

The goal of this action is to capture the reasoning and implementation text. As is the utility saves the information in a database within its operational directory. By default this is in the user's home directory. If the users's environment is lost, the reasoning logic is lost. This action will export these artifacts to be committed with the change request.

## Test Data Set
You have been provided an example backup database: `~/antigravity/agv2_sprint2readme/_gemini/antigravity/` You have complete authority to explore this backup. This is not the database for this running instance of the utility.  Within this database, find a project called "atc". Locate a prompt titled "Resize And Responsive Radar". The prompt will  beginning with:
```
The utility works perfectly. The spec called for an 800x800 radar screen. This does not work on some laptops. Change the screen to 700x700. <snip>
```
Associated with this prompt, you should find reasoning that include:
```
I've been examining the provided CSS snippet. My focus is the .radar-panel class, where I see a flexbox layout being used to center content within a container. <snip>
```

## Export Deliverable 
The goal of the Python export utility is to read a accept a command line argument that specifies a `--project|-p` and a `--conversation|-c`. It will export the prompt, the "Thought" blocks, and abstracts. We do not need the list of tools called, which might be tagged as "Analyzed", "Edited", "Ran", or "Searched". The primary tag is "Thought".

The output file will include text relevant to the decision making processes. The output will be a markdown file in _this_ project directory. Not the directory of the original project. It will be the operator's responsibility to move and commit the exported file.

The file name will be the project and the timestamp of the conversation. The file will begin with `# <conversation title>`. The user's prompt will begin the document as text. Each "Thought" reasoning text will be in a code block (```<snip>```<blank line>)

If there are embedded artifacts, they will be in subsections (```##<artifact name>\n<artifact>). Dump artifacts as code blocks.

