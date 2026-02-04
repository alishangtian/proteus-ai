---
name: deep-research
description: Comprehensive toolkit for conducting deep, multi-dimensional research
  using serper_search, web_crawler, and python_execute tools. Use when users need
  in-depth analysis of complex topics, including market research, technical investigations,
  academic literature reviews, fact-checking, and competitive analysis. This skill
  provides structured workflows for systematic information gathering, multi-source
  validation, critical analysis, and professional reporting.
allowed-tools:
  - python_execute
  - serper_search
  - web_crawler
---
# Deep Research Skill

## Overview

This skill enables Claude to conduct professional-grade deep research by following systematic methodologies that ensure depth, accuracy, and objectivity. It transforms general information gathering into structured research processes that incorporate multi-source validation, critical analysis, data synthesis, and comprehensive reporting.

## Core Principles of Deep Research

### 1. Depth Over Breadth
- Go beyond surface information to understand underlying mechanisms, context, and implications
- Answer not just "what" but also "why," "how," and "what if"
- Explore historical context, current state, and future trends

### 2. Multi-Source Verification
- Never rely on single sources for critical facts
- Cross-verify information across at least 2-3 independent sources
- Prioritize primary sources (original research, official documents) over secondary interpretations

### 3. Critical Evaluation
- Assess source credibility, author expertise, and potential biases
- Identify information gaps, contradictions, and uncertainties
- Distinguish between facts, opinions, and speculations

### 4. Structured Analysis
- Break down complex topics into logical components
- Use frameworks to analyze from multiple perspectives
- Create comparative analyses using tables and visualizations

### 5. Data-Driven Insights
- Support arguments with quantitative data when available
- Create visual representations of trends and relationships
- Calculate metrics, growth rates, and comparative statistics

## Research Framework

### Phase 1: Scope Definition & Planning
**Objective**: Clearly define research boundaries and objectives

**Key Activities**:
1. **Topic Clarification**: Restate the research question in your own words
2. **Scope Boundaries**: Determine temporal, geographical, and thematic limits
3. **Key Dimensions**: Identify main aspects to investigate (technical, market, competitive, regulatory, etc.)
4. **Success Criteria**: Define what constitutes a complete answer

**Tool Usage**:
- Use `python_execute` to create research plans and outlines
- Create mind maps or structured outlines to visualize research scope

### Phase 2: Information Gathering
**Objective**: Collect comprehensive, high-quality information

**Search Strategies**:
1. **Keyword Expansion**: Generate related terms, synonyms, and technical jargon
2. **Source Diversification**: Search across news, academic papers, industry reports, forums, official websites
3. **Iterative Refinement**: Use findings to discover new keywords and sources

**Tool Usage**:
- Use `serper_search` for broad information discovery
- Use `web_crawler` for deep dives into specific sources
- Implement systematic search patterns (see `references/search_patterns.md`)

### Phase 3: Source Evaluation & Validation
**Objective**: Assess information quality and reliability

**Evaluation Criteria**:
1. **Authority**: Author/organization credentials and expertise
2. **Accuracy**: Factual correctness and supporting evidence
3. **Currency**: Publication date and timeliness
4. **Objectivity**: Potential biases and balanced perspective
5. **Coverage**: Depth and completeness of information

**Validation Techniques**:
- Cross-reference key facts across multiple sources
- Check citations and references in academic/scientific content
- Verify statistics with original data sources

### Phase 4: Analysis & Synthesis
**Objective**: Transform information into insights

**Analytical Techniques**:
1. **Comparative Analysis**: Side-by-side comparison of options, technologies, or approaches
2. **Trend Analysis**: Identify patterns over time using available data
3. **SWOT Analysis**: Strengths, Weaknesses, Opportunities, Threats
4. **Root Cause Analysis**: Identify underlying factors and drivers
5. **Impact Assessment**: Evaluate potential consequences and implications

**Tool Usage**:
- Use `python_execute` for data analysis, visualization, and statistical calculations
- Create tables, charts, and diagrams to present findings
- Implement automated data processing for large datasets

### Phase 5: Reporting & Communication
**Objective**: Present findings in a clear, structured, actionable format

**Enhanced Report Templates**:
The deep-research skill now provides multiple template options to suit different research needs:

#### 📊 1. Standard Deep Research Template (`templates/standard.md`)
**Best for**: Comprehensive analysis, detailed investigations, formal reports
**Features**: 
- Complete 10-section structure with enhanced visual hierarchy
- Icon-based navigation and visual separation
- Built-in quality assessment and verification tracking
- Multiple analytical frameworks (SWOT, PESTEL, risk assessment)
- Research quality scoring card

#### 🚀 2. Quick Research Template (`templates/quick.md`)
**Best for**: Time-sensitive decisions, executive briefings, preliminary findings
**Features**:
- Single-page format (5-minute read time)
- Focus on 3 key findings and immediate actions
- Visual decision trees and summary tables
- Rapid implementation guidance

#### 🎓 3. Academic Research Template (`templates/academic.md`)
**Best for**: Literature reviews, academic papers, research proposals
**Features**:
- Formal academic structure (Abstract, Literature Review, Methodology, etc.)
- Statistical analysis reporting standards
- Theoretical framework integration
- Citation formats (APA, GB/T)
- Research ethics consideration

#### Template Selection Guide:
| Research Type | Recommended Template | Key Focus Areas |
|---------------|---------------------|-----------------|
| Market Analysis | Standard Template | Sections 3, 4, 5, 7, 9 |
| Technology Evaluation | Standard Template | Sections 2, 5, 6, 9 |
| Competitive Analysis | Standard Template | Sections 3, 5, 7, 9 |
| Executive Decision | Quick Template | Entire simplified structure |
| Literature Review | Academic Template | Sections 2, 3, 4, 7 |
| Research Proposal | Academic Template | Sections 1, 2, 3, 6 |

**Standard Report Structure** (Detailed Template):
1. **Executive Summary**: 3-5 sentence overview of key findings
2. **Introduction & Background**: Context and research objectives
3. **Methodology**: Approach and sources used with credibility assessment
4. **Findings**: Organized by key themes with supporting evidence
5. **Comparative Analysis**: Side-by-side comparison tables
6. **Comprehensive Analysis**: SWOT, PESTEL, risk assessment frameworks
7. **Data Visualization**: Mermaid diagrams and visual summaries
8. **Academic Rigor**: Statistical validation and theoretical grounding
9. **Conclusions & Recommendations**: Layered recommendations with timelines
10. **References**: Properly formatted source citations
11. **Appendix**: Research quality assessment and verification tracking

**Visual Elements**:
- Use Markdown tables with icon-based rating systems
- Create Mermaid diagrams for processes and relationships
- Embed relevant images when available
- Include data visualizations from Python analysis
- Use color-coded sections for better navigation

**Quality Enhancement Features**:
- Research confidence ratings for key findings
- Multi-source verification tracking tables
- Risk probability-impact matrices
- Implementation difficulty assessments
- Template-guided filling instructions## Tool-Specific Guidance

### serper_search Tool
**Best Practices**:
- Use specific, targeted queries rather than broad searches
- Combine multiple search terms with operators (site:, filetype:, intitle:)
- Search in different languages when researching international topics
- Set appropriate `max_results` based on research phase (5-10 for exploratory, 10-20 for comprehensive)

**Common Use Cases**:
- Initial exploratory research on unfamiliar topics
- Finding recent news and developments
- Discovering key industry players and thought leaders
- Locating academic papers and industry reports

### web_crawler Tool
**Best Practices**:
- Prioritize crawling authoritative sources (official websites, academic journals, reputable publications)
- Use `need_summary=true` for quick understanding of long documents
- Use `include_markdown=true` when detailed content analysis is needed
- Verify crawled content against search snippets to ensure relevance

**Common Use Cases**:
- Extracting detailed information from specific documents
- Analyzing full research papers or technical specifications
- Gathering data from structured sources (tables, lists, datasets)
- Monitoring updates from specific websites or blogs

### python_execute Tool
**Best Practices**:
- Use for data processing, analysis, and visualization
- Create reusable scripts for common research tasks
- Validate data quality and handle missing values appropriately
- Generate professional visualizations (charts, graphs, diagrams)

**Common Research Scripts**:
- Data collection and aggregation from multiple sources
- Statistical analysis and trend calculation
- Text analysis (sentiment, keyword extraction, topic modeling)
- Visualization generation (see `scripts/visualization_templates.py`)

## Quality Assurance Checklist

Before finalizing any research output, verify:

- [ ] All critical facts are verified by at least 2 independent sources
- [ ] Sources are properly cited with clickable links
- [ ] Analysis includes both supporting and contradictory evidence
- [ ] Limitations and uncertainties are explicitly acknowledged
- [ ] Visual elements enhance understanding rather than distract
- [ ] Recommendations are actionable and evidence-based
- [ ] Report structure follows professional standards



## Template Usage Guidance

### How to Select the Right Template
1. **Assess your research purpose**:
   - *Decision support* → Quick Template
   - *Comprehensive analysis* → Standard Template  
   - *Academic publication* → Academic Template

2. **Consider your audience**:
   - *Executives* → Quick Template (concise, actionable)
   - *Technical teams* → Standard Template (detailed, analytical)
   - *Academic reviewers* → Academic Template (formal, rigorous)

3. **Evaluate time constraints**:
   - *<2 hours* → Quick Template
   - *2-8 hours* → Standard Template
   - *>8 hours* → Academic Template

### Best Practices for Template Usage
1. **Start with the executive summary** - Even in detailed reports, begin with the key takeaways
2. **Use the quality assessment tools** - Apply the scoring cards and verification tracking
3. **Customize, don't just fill** - Adapt templates to your specific research context
4. **Leverage visual elements** - Use diagrams and tables to enhance understanding
5. **Maintain source integrity** - Always include clickable links and proper citations

### Common Template Customizations
- **Combine templates**: Use Quick Template structure with Standard Template depth
- **Section prioritization**: Focus on the most relevant sections for your research
- **Industry-specific adaptations**: Modify terminology and examples for your domain
- **Length adjustments**: Expand or condense sections based on importance

### Template Evolution
These templates are continuously improved based on user feedback and research best practices. For the latest versions and additional templates, check the assets directory.## Quick Start Guide

### For New Research Topics:
1. Use `serper_search` with 2-3 keyword variations to scope the landscape
2. Identify 3-5 authoritative sources from initial results
3. Use `web_crawler` to extract detailed information from key sources
4. Create a structured outline using `python_execute` to organize findings
5. Build comparative tables for key dimensions
6. Synthesize insights and generate final report

**Pro Tip**: Check the `examples/` directory for industry-specific research templates and methodologies.

### For Fact-Checking:
1. Use `serper_search` to find multiple sources mentioning the claim
2. Crawl original sources using `web_crawler` to verify context
3. Cross-reference dates, numbers, and statements across sources
4. Document verification process and source discrepancies
## Examples & Case Studies

The `examples/` directory provides real-world case studies demonstrating how to apply the deep-research skill to different types of research projects.

### Available Examples

#### 1. Market Analysis Example (`examples/market_analysis_example.md`)
**Use Case**: Analyzing market opportunities for generative AI in content creation  
**Key Components**:
- Market sizing and growth trend analysis
- Competitive landscape assessment  
- PESTEL and SWOT frameworks application
- Market entry recommendations

#### 2. Technology Evaluation Example (`examples/technology_evaluation_example.md`)
**Use Case**: Comparative evaluation of large language models for enterprise adoption  
**Key Components**:
- Performance benchmarking across multiple LLMs
- Cost-benefit analysis and ROI calculation
- Technology adoption lifecycle assessment
- Implementation roadmap development

#### 3. Academic Literature Review Example (`examples/academic_literature_review_example.md`)
**Use Case**: Systematic literature review of deep learning in medical imaging  
**Key Components**:
- Literature search strategy and methodology
- Research gap identification and analysis
- Theoretical framework development
- Future research directions

### How to Use Examples

1. **Learning Reference**: Study the examples to understand complete research workflows
2. **Template Application**: See how templates are applied in real scenarios
3. **Methodology Adaptation**: Adapt research methods to your specific needs
4. **Custom Project Creation**: Use examples as starting points for your own research

### Example Selection Guide

| Research Type | Recommended Example | Primary Template | Key Skills Demonstrated |
|---------------|---------------------|------------------|-------------------------|
| Business/Market Research | Market Analysis Example | `templates/standard.md` | Market analysis, competitive assessment, strategic recommendations |
| Technology Selection | Technology Evaluation Example | `templates/standard.md` | Technical comparison, cost analysis, implementation planning |
| Academic Research | Academic Literature Review Example | `templates/academic.md` | Literature review, theoretical analysis, research methodology |

### Best Practices from Examples

1. **Start with Clear Objectives**: Each example begins with well-defined research questions
2. **Use Multiple Frameworks**: Examples show how to combine different analytical frameworks
3. **Prioritize Data Quality**: Emphasis on credible data sources and verification
4. **Focus on Actionable Insights**: All examples conclude with practical recommendations

### Customizing Examples

You can adapt these examples for your own research by:
- Modifying the research questions and scope
- Replacing example data with your specific dataset
- Adjusting analytical frameworks to match your domain
- Customizing report structure for your audience

For detailed guidance on each example, refer to the `examples/README.md` file.


## References

For detailed guidance on specific research aspects, consult:
- `references/research_frameworks.md` - Detailed analytical frameworks
- `references/source_evaluation.md` - Comprehensive source assessment criteria
- `references/visualization_guide.md` - Data visualization best practices
- `references/search_patterns.md` - Effective search strategies and patterns
- `references/template_selection_guide.md` - Template selection and usage guide
- `scripts/data_analysis_templates.py` - Python templates for common analyses