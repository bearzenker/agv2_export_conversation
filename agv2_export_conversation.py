#!/usr/bin/env python3
"""
Google Antigravity V2 Decision Export Utility
Exports prompt, thoughts, and artifacts from a conversation to Markdown.
"""

import os
import re
import sys
import json
import argparse
import sqlite3

def parse_varint(data, pos):
    val = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        val |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, pos

def parse_summaries_pb(pb_path):
    if not os.path.exists(pb_path):
        return []
    
    with open(pb_path, 'rb') as f:
        content = f.read()
        
    uuid_pattern = re.compile(b'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    entries = []
    
    for m in uuid_pattern.finditer(content):
        uuid = m.group(0).decode('ascii')
        start = m.start()
        
        # Protobuf tag check: \x0a\x24 (field 1, length 36)
        if start >= 2 and content[start-2] == 0x0a and content[start-1] == 0x24:
            curr = m.end()
            if curr < len(content) and content[curr] == 0x12:
                curr += 1
                msg_len, curr = parse_varint(content, curr)
                msg_end = curr + msg_len
                
                title = ""
                if curr < len(content) and content[curr] == 0x0a:
                    curr += 1
                    title_len, curr = parse_varint(content, curr)
                    title = content[curr:curr+title_len].decode('utf-8', errors='ignore')
                
                ws_match = re.search(b'file:///[a-zA-Z0-9_:/\\-\\.]+', content[m.end():msg_end])
                ws_url = ws_match.group(0).decode('utf-8') if ws_match else ""
                project = os.path.basename(ws_url.rstrip('/')) if ws_url else ""
                
                entries.append({
                    'uuid': uuid,
                    'title': title,
                    'project': project,
                    'workspace_url': ws_url
                })
    return entries

def find_fallback_title(brain_dir, transcript_path):
    if os.path.exists(transcript_path):
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    step = json.loads(line)
                    content = step.get('content', '')
                    match = re.search(r'# USER Objective:\s*(.*?)\s*(\n|$)', content)
                    if match:
                        return match.group(1).strip()
        except Exception:
            pass
            
    for filename, prefixes in [
        ('implementation_plan.md', ["Implementation Plan - ", "Implementation Plan: "]),
        ('walkthrough.md', ["Walkthrough - ", "Walkthrough: "])
    ]:
        path = os.path.join(brain_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('# '):
                            header = line[2:].strip()
                            for prefix in prefixes:
                                if header.startswith(prefix):
                                    header = header[len(prefix):]
                            return header
            except Exception:
                pass
                
    return "Untitled Conversation"

def find_fallback_project(db_dir, convo_id):
    db_path = os.path.join(db_dir, 'conversations', f"{convo_id}.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            rows = conn.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'").fetchall()
            if rows:
                blob = rows[0][0]
                match = re.search(rb'file:///([^\s\x00-\x1f\x7f-\xff]+)', blob)
                if match:
                    ws_url = match.group(0).decode('utf-8', errors='ignore')
                    return os.path.basename(ws_url.rstrip('/'))
        except Exception:
            pass
    return "unknown_project"

def scan_brain_directory(db_dir):
    entries = []
    brain_path = os.path.join(db_dir, 'brain')
    if not os.path.exists(brain_path):
        return entries
        
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    for name in os.listdir(brain_path):
        if uuid_pattern.match(name):
            brain_dir = os.path.join(brain_path, name)
            if os.path.isdir(brain_dir):
                logs_dir = os.path.join(brain_dir, '.system_generated', 'logs')
                transcript_path = os.path.join(logs_dir, 'transcript_full.jsonl')
                if not os.path.exists(transcript_path):
                    transcript_path = os.path.join(logs_dir, 'transcript.jsonl')
                
                title = find_fallback_title(brain_dir, transcript_path)
                project = find_fallback_project(db_dir, name)
                
                entries.append({
                    'uuid': name,
                    'title': title,
                    'project': project,
                    'workspace_url': ''
                })
    return entries

def wrap_code_block(content):
    if "```" in content:
        max_backticks = 0
        for m in re.finditer(r'`+', content):
            max_backticks = max(max_backticks, len(m.group(0)))
        wrap_ticks = '`' * max(3, max_backticks + 1)
        return f"{wrap_ticks}\n{content}\n{wrap_ticks}"
    else:
        return f"```\n{content}\n```"

def main():
    parser = argparse.ArgumentParser(description="Export Antigravity V2 conversation details and artifacts to Markdown.")
    parser.add_argument("-p", "--project", help="Name of the project (e.g. 'atc')")
    parser.add_argument("-c", "--conversation", help="Conversation UUID or conversation title search term")
    parser.add_argument("-l", "--list", action="store_true", help="List available projects, or list conversations within a project if -p/--project is specified")
    parser.add_argument("-d", "--db-dir", default="~/.gemini/antigravity", help="Database directory path")
    parser.add_argument("-o", "--output-dir", default=".", help="Directory to save the exported markdown file")
    
    args = parser.parse_args()
    
    # Expand user directory in paths
    db_dir = os.path.abspath(os.path.expanduser(args.db_dir))
    output_dir = os.path.abspath(os.path.expanduser(args.output_dir))
    
    if not os.path.exists(db_dir):
        print(f"Error: Database directory '{db_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    pb_path = os.path.join(db_dir, "agyhub_summaries_proto.pb")
    
    # Get conversation list
    entries = parse_summaries_pb(pb_path)
    
    # Fallback to scanning brain directory if empty or missing
    if not entries:
        entries = scan_brain_directory(db_dir)
    else:
        # Merge scan entries for robustness (if some are in brain but not in pb)
        scan_entries = scan_brain_directory(db_dir)
        known_uuids = {e['uuid'] for e in entries}
        for se in scan_entries:
            if se['uuid'] not in known_uuids:
                entries.append(se)
                
    # Handle listing mode
    if args.list:
        if args.project:
            project_entries = [e for e in entries if e['project'].lower() == args.project.lower()]
            if not project_entries:
                print(f"Error: No conversations found for project '{args.project}'.", file=sys.stderr)
                available_projects = sorted(list(set(e['project'] for e in entries if e['project'])))
                if available_projects:
                    print("Available projects:", file=sys.stderr)
                    for proj in available_projects:
                        print(f"  - {proj}", file=sys.stderr)
                sys.exit(1)
                
            print(f"Available conversations for project '{args.project}':")
            for e in project_entries:
                print(f"  - UUID: {e['uuid']}, Title: '{e['title']}'")
        else:
            projects = sorted(list(set(e['project'] for e in entries if e['project'])))
            if not projects:
                print("No projects found.")
            else:
                print("Available projects:")
                for proj in projects:
                    print(f"  - {proj}")
        sys.exit(0)
        
    # If not in listing mode, both --project and --conversation are required
    if not args.project or not args.conversation:
        parser.error("the following arguments are required: -p/--project, -c/--conversation (unless --list is specified)")
        
    # Filter by project
    project_entries = [e for e in entries if e['project'].lower() == args.project.lower()]
    
    if not project_entries:
        print(f"Error: No conversations found for project '{args.project}'.", file=sys.stderr)
        available_projects = sorted(list(set(e['project'] for e in entries if e['project'])))
        if available_projects:
            print("Available projects:", file=sys.stderr)
            for proj in available_projects:
                print(f"  - {proj}", file=sys.stderr)
        sys.exit(1)
        
    # Match conversation
    target_uuid = args.conversation
    matched_entry = None
    
    # Check exact UUID match first
    for e in project_entries:
        if e['uuid'] == target_uuid:
            matched_entry = e
            break
            
    # Check case-insensitive substring match in title
    if not matched_entry:
        matches = []
        for e in project_entries:
            if target_uuid.lower() in e['title'].lower():
                matches.append(e)
        if len(matches) == 1:
            matched_entry = matches[0]
        elif len(matches) > 1:
            print(f"Error: Multiple conversations match search term '{target_uuid}':", file=sys.stderr)
            for m in matches:
                print(f"  - UUID: {m['uuid']}, Title: '{m['title']}'", file=sys.stderr)
            sys.exit(1)
            
    if not matched_entry:
        print(f"Error: No conversation matches '{target_uuid}' in project '{args.project}'.", file=sys.stderr)
        print("Available conversations for this project:", file=sys.stderr)
        for e in project_entries:
            print(f"  - UUID: {e['uuid']}, Title: '{e['title']}'", file=sys.stderr)
        sys.exit(1)
        
    convo_id = matched_entry['uuid']
    title = matched_entry['title']
    project = matched_entry['project']
    
    print(f"Found conversation:")
    print(f"  Project: {project}")
    print(f"  UUID: {convo_id}")
    print(f"  Title: {title}")
    
    # Paths to transcript
    brain_dir = os.path.join(db_dir, 'brain', convo_id)
    logs_dir = os.path.join(brain_dir, '.system_generated', 'logs')
    
    transcript_path = os.path.join(logs_dir, 'transcript_full.jsonl')
    if not os.path.exists(transcript_path):
        transcript_path = os.path.join(logs_dir, 'transcript.jsonl')
        
    if not os.path.exists(transcript_path):
        print(f"Error: Transcript file not found in logs directory '{logs_dir}'.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Reading transcript from {transcript_path}...")
    
    prompt = None
    thoughts = []
    timestamp = None
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                step = json.loads(line)
            except Exception:
                continue
            
            if timestamp is None and 'created_at' in step:
                timestamp = step['created_at']
                
            if step.get('type') == 'USER_INPUT' and prompt is None:
                content = step.get('content', '')
                match = re.search(r'<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>', content, re.DOTALL)
                if match:
                    prompt = match.group(1).strip()
                else:
                    prompt = content.strip()
                    
            if step.get('type') == 'PLANNER_RESPONSE' and step.get('source') == 'MODEL':
                thinking = step.get('thinking', '')
                if thinking:
                    thoughts.append(thinking.strip())
                    
    if not prompt:
        prompt = "No user prompt found in transcript."
        
    if not timestamp:
        timestamp = "unknown_time"
        
    # Format markdown output
    output_lines = []
    output_lines.append(f"# {title}\n")
    
    formatted_prompt = ["User prompt:\n"]
    for line in prompt.splitlines():
        # Indent headers by an extra level
        indented_line = re.sub(r'^(\s*)(#+)', r'\1#\2', line)
        if indented_line:
            formatted_prompt.append(f"> {indented_line}\n")
        else:
            formatted_prompt.append(">\n")
            
    output_lines.append("".join(formatted_prompt) + "\n")
    
    for t in thoughts:
        output_lines.append(f"```\n{t}\n```\n\n")
        
    # Read and embed artifacts
    artifacts = []
    if os.path.exists(brain_dir):
        for f_name in os.listdir(brain_dir):
            f_path = os.path.join(brain_dir, f_name)
            if os.path.isfile(f_path) and not f_name.startswith('.') and not f_name.endswith('.json'):
                artifacts.append(f_name)
                
    artifacts.sort()
    
    for art in artifacts:
        art_path = os.path.join(brain_dir, art)
        try:
            with open(art_path, 'r', encoding='utf-8') as f:
                art_content = f.read()
            output_lines.append(f"## {art}\n{wrap_code_block(art_content)}\n\n")
        except Exception as e:
            print(f"Warning: Could not read artifact '{art}': {e}", file=sys.stderr)
            
    # Clean timestamp for filename (replace colons and keep it clean)
    clean_ts = timestamp.replace(':', '-')
    filename = f"{project}_{clean_ts}.md"
    output_filepath = os.path.join(output_dir, filename)
    
    os.makedirs(output_dir, exist_ok=True)
    with open(output_filepath, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
        
    print(f"Successfully exported decision README to: {output_filepath}")

if __name__ == "__main__":
    main()
