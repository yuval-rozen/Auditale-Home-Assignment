# AI Collaboration Evidence — Customer Health App

**Author:** Yuval Rozen  
**Project:** Customer Health App  

---

## 1. Documentation of AI Tool Usage

From the very beginning of this project, I used AI (ChatGPT 5) as a collaborative partner to accelerate and sharpen my work. 
One of the first areas where AI proved valuable was in the selection of technologies. 
I explored different backend frameworks, databases, and deployment approaches, and AI helped me weigh the trade-offs. 
Through those discussions, I reached the decision to build the application with FastAPI for the backend, PostgreSQL as the database, and NGINX to serve the frontend, all orchestrated with Docker Compose. 
This combination struck the right balance between technologies i already knew and pragmatic simplicity for a project of this scope.

AI also played a role in shaping the system architecture itself. Rather than starting from scratch, I refined an AI-suggested baseline into the three-container structure (backend, frontend, database) 
that I eventually implemented (also with AI help, took a few iterations). 
Having this foundation allowed me to focus on logic and usability rather than wiring issues.

In the database design, I leaned on AI to help map out the entities and relationships needed to support realistic seeding and scoring. 
Together, we converged on the tables, each seeded with distributions that reflected real-world SaaS dynamics (such as enterprise vs. SMB vs. startup behavior, on-time vs. late payments, and variable adoption of key features). 
This segment aware approach produced test data that made the dashboard more credible and the scoring outcomes more meaningful.

When it came to researching the scoring factors and calculation methods, I used AI not only to brainstorm possible health indicators but also to refine them into a structured methodology. 
We debated time windows (30-day vs. 90-day), weighting schemes, and how to handle edge cases like customers without any billing history. 
The resulting design included smoothing and normalization rules to prevent extreme or misleading results.

Another way I leveraged AI was in drafting prompts for myself to use in separate chats. 
I realized that by asking AI to write a good prompt for another AI session (for example, when creating a methodology explanation document or an architecture diagram request), 
I could bootstrap a much higher quality output. 
It worked well: the prompts were sharper, and the results I got back in those separate chats were more professional and structured.

Finally, AI assisted me in drafting and polishing documentation. 
Whether it was the architecture description, the explanation of health score calculations, or this collaboration evidence report itself, 
I found that AI could generate a strong baseline draft. 
I then reviewed, edited, and refined that draft to ensure accuracy and voice. 
This workflow saved me significant time and helped me elevate the professionalism of the documents and project files.

## 2. Quality of Research & Implementation Decisions

- **Database & Runtime**: PostgreSQL was chosen for realism and migration path. AI helped justify healthchecks and explicit image pinning to prevent version mismatch.  
- **Nginx Static + API Proxy**: AI recommended proxying `/api/*` to the backend to avoid CORS and simplify frontend calls.  
- **Segment-Aware Seeding**: Ensuring enterprise vs. SMB vs. startup distributions made the dashboard feel credible.  
- **Scoring Windows & Weights**: Login/adoption (engagement), support/billing (friction), API trend (momentum). Neutral scores avoided punishing new customers.  
- **Smoothing & Capping**: Logins capped at 20→100; invoice score neutral if missing; API trend smoothed.  
- **JSON Shape**: CamelCase keys (`healthScore`) exposed to frontend with Pydantic aliases—AI suggested this alignment to prevent mismatched UI expectations.  
- **Test Coverage Policy**: AI helped me enforce `pytest --cov --cov-fail-under=80`.

---

## 3. Evidence of Iterating on AI-Generated Suggestions

During the interview, I would also be able to share live examples from my actual AI-assisted chats. 
These illustrate not only the outcomes but also the iterative process—how I framed a problem, how AI responded, and how I refined or adapted the suggestions into the final implementation. 

---

## 4. Summary

AI collaboration accelerated my work by providing **research, architectural scaffolding, and bug resolution strategies**. 
I still made the final calls for example: how to design seeding distributions, how to weigh factors, how to design the frontend etc.  

