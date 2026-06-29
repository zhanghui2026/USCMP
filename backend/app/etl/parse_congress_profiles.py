"""Parse congress member profiles from Markdown files.

Extracts:
- Basic info (name, party, state, district, birth, education)
- China stance summary
- Core political positions
- Comprehensive evaluation
- Media reports (for controversies)
- Committee membership from directory structure
"""

import os
import re
from pathlib import Path
from typing import Optional


def parse_member_file(filepath: Path) -> dict:
    """Parse a single member markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {
        'filename': filepath.stem,
        'directory': str(filepath.parent.name),
        'full_name': None,
        'display_name': None,
        'party': None,
        'state': None,
        'district': None,
        'birth_date': None,
        'education': None,
        'china_stance': None,
        'core_positions': None,
        'comprehensive_evaluation': None,
        'media_reports': None,
        'committee_from_dir': None,
        'career_history': None,
        'policy_positions': None,
    }

    lines = content.split('\n')
    
    # Skip YAML front matter (between --- lines)
    start_idx = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start_idx = i + 1
                break
    
    # Extract display name from first # heading after front matter
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        if line.startswith('# '):
            name_line = line[2:].strip()
            # Remove Chinese name in parentheses
            name_line = re.sub(r'[（(].*?[）)]', '', name_line).strip()
            # Remove descriptions after em-dash or en-dash (not hyphen)
            name_line = re.sub(r'\s*[—–]\s*.+$', '', name_line).strip()
            # Remove quotes around nicknames: James "Jim" Himes -> James Himes
            name_line = re.sub(r'\s*"[^"]*"\s*', ' ', name_line).strip()
            # Clean up extra spaces
            name_line = ' '.join(name_line.split())
            result['display_name'] = name_line
            break

    # Parse basic info - try table format first, then bold-label format
    for i, line in enumerate(lines):
        # Table format: | **Field** | Value |
        if '**全名**' in line or '**Full Name**' in line:
            match = re.search(r'\|\s*\*\*.*?\*\*\s*\|\s*(.+?)\s*\|', line)
            if match:
                result['full_name'] = match.group(1).strip()
            else:
                # Bold-label format: **全名：** Value
                match = re.search(r'\*\*.*?\*\*[：:]\s*(.+)', line)
                if match:
                    result['full_name'] = match.group(1).strip()
        
        if '**党派**' in line or '**Party**' in line:
            match = re.search(r'\|\s*\*\*.*?\*\*\s*\|\s*(.+?)\s*\|', line)
            if match:
                party_text = match.group(1).strip()
            else:
                match = re.search(r'\*\*.*?\*\*[：:]\s*(.+)', line)
                if match:
                    party_text = match.group(1).strip()
                else:
                    party_text = None
            
            if party_text:
                if '共和' in party_text or 'Republican' in party_text.lower():
                    result['party'] = 'Republican'
                elif '民主' in party_text or 'Democratic' in party_text.lower():
                    result['party'] = 'Democratic'
                elif '独立' in party_text or 'Independent' in party_text.lower():
                    result['party'] = 'Independent'

        if '**选区**' in line or '**District**' in line:
            match = re.search(r'\|\s*\*\*.*?\*\*\s*\|\s*(.+?)\s*\|', line)
            if match:
                district_text = match.group(1).strip()
            else:
                match = re.search(r'\*\*.*?\*\*[：:]\s*(.+)', line)
                if match:
                    district_text = match.group(1).strip()
                else:
                    district_text = None
            
            if district_text:
                state_match = re.search(r'([A-Za-z]{2})', district_text)
                if state_match:
                    result['state'] = state_match.group(1)
                result['district'] = district_text

        if '**出生**' in line or '**Born**' in line:
            match = re.search(r'\|\s*\*\*.*?\*\*\s*\|\s*(.+?)\s*\|', line)
            if match:
                result['birth_date'] = match.group(1).strip()
            else:
                match = re.search(r'\*\*.*?\*\*[：:]\s*(.+)', line)
                if match:
                    result['birth_date'] = match.group(1).strip()

        if '**教育**' in line or '**Education**' in line:
            match = re.search(r'\|\s*\*\*.*?\*\*\s*\|\s*(.+?)\s*\|', line)
            if match:
                result['education'] = match.group(1).strip()
            else:
                match = re.search(r'\*\*.*?\*\*[：:]\s*(.+)', line)
                if match:
                    result['education'] = match.group(1).strip()

    # Extract china stance (try multiple section names)
    china_section = extract_section(content, '对华立场分析', ['核心政治主张', '利益关系', '媒体报道', '综合评价'])
    if not china_section:
        china_section = extract_section(content, '对华立场概要', ['关键涉华记录', '资金来源', '核心政治主张', '利益关系', '媒体报道', '综合评价'])
    if china_section:
        result['china_stance'] = china_section.strip()

    # Extract key China records (关键涉华记录)
    china_records = extract_section(content, '关键涉华记录', ['资金来源', '核心政治主张', '利益关系', '媒体报道', '综合评价'])
    if china_records:
        # Append to china_stance if exists
        if result['china_stance']:
            result['china_stance'] = result['china_stance'] + '\n\n### 关键涉华记录\n' + china_records.strip()
        else:
            result['china_stance'] = '### 关键涉华记录\n' + china_records.strip()

    # Extract expected China stance (预期对华立场) for very short files
    if not result['china_stance']:
        for line in lines:
            if '**预期对华立场**' in line:
                match = re.search(r'\*\*预期对华立场\*\*[：:]\s*(.+)', line)
                if match:
                    result['china_stance'] = '预期对华立场：' + match.group(1).strip()
                    break

    # Extract core positions
    core_section = extract_section(content, '核心政治主张', ['利益关系', '媒体报道', '综合评价'])
    if core_section:
        result['core_positions'] = core_section.strip()

    # Extract comprehensive evaluation
    eval_section = extract_section(content, '综合评价', ['数据来源', '更新时间', '*'])
    if eval_section:
        result['comprehensive_evaluation'] = eval_section.strip()

    # Extract media reports
    media_section = extract_section(content, '媒体报道', ['综合评价', '数据来源'])
    if media_section:
        result['media_reports'] = media_section.strip()

    # Extract career history (政治生涯 / 政治履历 / 早期生涯与教育)
    career_section = extract_section(content, '政治生涯', ['关键委员会', '主要政策', '对华立场', '核心政治主张', '利益关系', '媒体报道', '综合评价'])
    if not career_section:
        career_section = extract_section(content, '政治履历', ['关键委员会', '主要政策', '对华立场', '核心政治主张', '利益关系', '媒体报道', '综合评价'])
    if not career_section:
        career_section = extract_section(content, '早期生涯', ['政治生涯', '政治履历', '关键委员会', '主要政策', '对华立场', '核心政治主张', '利益关系', '媒体报道', '综合评价'])
    if career_section:
        result['career_history'] = career_section.strip()

    # Extract policy positions (主要政策立场 / 政策立场)
    policy_section = extract_section(content, '主要政策立场', ['对华立场', '核心政治主张', '利益关系', '媒体报道', '综合评价', '近年动态'])
    if not policy_section:
        policy_section = extract_section(content, '政策立场', ['对华立场', '核心政治主张', '利益关系', '媒体报道', '综合评价', '近年动态'])
    if policy_section:
        result['policy_positions'] = policy_section.strip()

    # Extract committee from directory
    dir_name = filepath.parent.name
    if dir_name.startswith('committee-'):
        result['committee_from_dir'] = dir_name.replace('committee-', '').replace('-', ' ').title()
    elif dir_name == 'leadership':
        result['committee_from_dir'] = 'Leadership'
    elif dir_name == 'no-committee':
        result['committee_from_dir'] = None

    return result


def extract_section(content: str, start_marker: str, end_markers: list[str]) -> Optional[str]:
    """Extract a section from markdown content."""
    lines = content.split('\n')
    in_section = False
    section_lines = []
    
    for line in lines:
        if start_marker in line and (line.startswith('##') or line.startswith('###')):
            in_section = True
            continue
        
        if in_section:
            # Check for end markers
            for marker in end_markers:
                if marker in line and (line.startswith('##') or line.startswith('###')):
                    return '\n'.join(section_lines)
            
            section_lines.append(line)
    
    return '\n'.join(section_lines) if section_lines else None


def parse_all_members(base_dir: Path) -> list[dict]:
    """Parse all member files from the congress-data directory."""
    members = []
    output_dir = base_dir / 'congress-data' / 'output'
    
    if not output_dir.exists():
        print(f"Directory not found: {output_dir}")
        return members
    
    # Walk through all directories
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('.md'):
                filepath = Path(root) / file
                member = parse_member_file(filepath)
                members.append(member)
    
    return members


def build_name_to_id_mapping(db_members: list) -> dict:
    """Build mapping from member names to IDs."""
    name_to_id = {}
    
    for m in db_members:
        # Primary key: canonical_name (Chinese name)
        if m.canonical_name:
            name_to_id[m.canonical_name.lower()] = m.id
        
        # Secondary key: display_name
        if m.display_name:
            name_to_id[m.display_name.lower()] = m.id
        
        # Also try English name variations
        if m.display_name:
            # Remove titles and suffixes
            clean_name = m.display_name.replace('Rep. ', '').replace('Sen. ', '')
            clean_name = re.sub(r'\s+(Jr\.|Sr\.|III|II|IV)$', '', clean_name)
            name_to_id[clean_name.lower()] = m.id
    
    return name_to_id


def match_member_to_id(parsed_member: dict, name_to_id: dict) -> Optional[str]:
    """Match a parsed member to a database member ID."""
    display_name = parsed_member.get('display_name', '')
    full_name = parsed_member.get('full_name', '')
    
    # Try exact match on display_name
    if display_name:
        key = display_name.lower()
        if key in name_to_id:
            return name_to_id[key]
    
    # Try exact match on full_name
    if full_name:
        key = full_name.lower()
        if key in name_to_id:
            return name_to_id[key]
    
    # Try fuzzy match (last name + first name)
    if display_name:
        parts = display_name.split()
        if len(parts) >= 2:
            # Try "Last, First" format
            last_first = f"{parts[-1]}, {' '.join(parts[:-1])}".lower()
            if last_first in name_to_id:
                return name_to_id[last_first]
    
    return None


if __name__ == '__main__':
    base_dir = Path('data/congress-profiles')
    members = parse_all_members(base_dir)
    
    print(f"Parsed {len(members)} members")
    
    # Count by party
    parties = {}
    for m in members:
        p = m.get('party') or 'Unknown'
        parties[p] = parties.get(p, 0) + 1
    print(f"By party: {parties}")
    
    # Count by committee
    committees = {}
    for m in members:
        c = m.get('committee_from_dir') or 'None'
        committees[c] = committees.get(c, 0) + 1
    print(f"By committee: {committees}")
    
    # Show sample
    if members:
        print("\nSample member:")
        sample = members[0]
        for k, v in sample.items():
            if v:
                val = str(v)[:100]
                print(f"  {k}: {val}")
