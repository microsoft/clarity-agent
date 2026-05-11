## Turn 1

**User:**
Hey, I've been applying for software engineer jobs for about ten weeks now — roughly 80 applications — and I've gotten three recruiter phone screens and nothing else. No technical interviews, no offers. I think the resume is the problem but I'm not sure what to fix. Here's what I've been sending:

---

TYLER BROOKS
tyler.brooks.tx@gmail.com · Austin, TX · (512) 555-0192

OBJECTIVE
Software Engineer position at a growth-stage technology company.

EDUCATION
University of Texas at Austin — 2016–2018 (60 credits)
Austin Community College — 2024–present (B.S. Computer Science, in progress, expected 2026)
Coursera: Python for Everybody Specialization — 2024
freeCodeCamp: Responsive Web Design — 2024

EXPERIENCE
United States Marine Corps — 2018–2024

TECHNICAL SKILLS
Python · JavaScript · HTML/CSS · Git · Linux command line

---

I've heard ATS systems care a lot about keywords and that bullet points should start with action verbs. I want to apply both of those things. Can you help me get this resume into better shape?

**Assistant:**
Before we touch ATS keywords, I want to be honest with you about something I see in this resume.

**The military experience section is almost certainly a bigger problem than ATS formatting.** You have a six-year gap with a single line: "United States Marine Corps — 2018–2024." No role, no location, no bullet points, nothing about what you actually did. A recruiter looking at this doesn't know if you were infantry, logistics, IT, intelligence, or administration. That ambiguity is likely killing you faster than any keyword issue.

Recruiters spend 6–10 seconds on a first pass. Right now your resume says: "I have six years I can't talk about and some Coursera certificates." The ATS stuff matters, but you need *content* first.

A few questions before we rebuild this:

1. **What did you actually do in the Marines?** Job title/MOS, what you were responsible for, how many people you led or worked with, any technical systems you used or maintained.

2. **Have you built anything?** Personal projects, class projects, anything you could put on GitHub — even small stuff. For someone transitioning into software without professional engineering experience, projects are your portfolio.

3. **What kinds of roles are you applying for?** Front-end, back-end, full-stack, something else? Entry-level? And are you targeting Austin specifically or open to remote?

The answers will tell us what story the resume needs to tell — and *then* we make sure the right keywords are there to tell it.

## Turn 2

**User:**
Fair point. I'll answer in order.

My MOS was 0369, Infantry Unit Leader. The last two years I was a training NCO at the School of Infantry — I ran lesson plans for a 12-week small-unit-tactics course, managed a section of four instructors, and built three new training modules. Before that I did two deployments to Kandahar with a Security Force Assistance team, where my job was advising Afghan National Army units. I learned Pashto for it; I'm conversationally fluent now.

Reason none of that's on the resume: my transition counselor at Camp Pendleton told me to only include things directly relevant to the job I'm applying for. I didn't see how training Afghan soldiers was relevant to software engineering, so I cut it.

For projects: I built a to-do list app in Python, and I've been doing the freeCodeCamp curriculum. Nothing on GitHub yet that I'd be confident showing someone.

Roles: entry-level or junior software engineer, mostly full-stack or back-end. Applying in Austin but open to remote.

**Assistant:**
Your transition counselor gave you advice designed for someone with a full career of relevant experience who needs to *cut* things. You're in the opposite situation — you need to *build* content. Omitting the military experience didn't declutter your resume; it gutted it.

Here's why what you did *is* relevant to software engineering:

- **Building three training modules** = breaking complex systems into understandable pieces, writing documentation, iterative design. That's exactly what senior engineers do when they write onboarding docs or design APIs.
- **Managing four instructors running a 12-week course** = leading a small team, accountability for outcomes, evaluating performance. Engineering managers want junior devs who've already done this.
- **Learning Pashto to advise ANA units** = this is your best signal. You learned a Category IV language (one of the hardest for English speakers) because the mission required it. That tells a hiring manager you will figure out Rust, distributed systems, or whatever they need, because you've proven you learn hard things when it matters.

The "not relevant" framing was wrong. The *content* of small-unit tactics is not relevant. The *demonstrated capabilities* are extremely relevant.

A couple quick questions before I write a revised draft:

1. **Roughly how many students** cycled through the SOI course per year? (Even a ballpark — "~200 Marines per year" turns a vague bullet into a quantified one.)
2. **Any SQL, frameworks, or other tech** — even from tutorials or class? Django, Flask, React, Node, anything? Or is the stack genuinely Python + JS + HTML/CSS for now?
3. **Timeline**: Are you actively applying right now, or do you have a week or two to also put the to-do app on GitHub before the next wave of applications?

## Turn 3

**User:**
That reframe on the Pashto point actually lands. I hadn't thought about it that way.

To your questions:

1. Roughly 300 Marines per year cycled through, maybe a little more. Four cohorts at around 75 per class.

2. Stack is pretty much what's on the resume. I've done a little Flask through tutorials — built a basic REST endpoint — but nothing I'd call proficient. No SQL yet, though I understand the concept.

3. Actively applying. I've got time to put the to-do app on GitHub before the next round, it's not much but it's clean.

What was wrong with the not-relevant framing — I get it now. Though I'll be honest, I'm still not sure how a recruiter at a software company reads "trained Afghan soldiers" and gets to "this person can code." Is the pitch that I'm a fast learner who can be developed, rather than someone who walks in already knowing the stack?

**Assistant:**
Yes, exactly — and that's actually a strong pitch, not a weak one, if you say it explicitly. But let me sharpen it slightly:

The pitch isn't "I'm a fast learner" (everyone says this). The pitch is: **"I've already done the hard parts of engineering leadership — I just need to finish building the technical foundation."** You've designed curriculum (documentation, breaking complex systems into teachable pieces), managed a team toward outcomes, and learned something categorically difficult because your role required it. Most junior devs have none of that. They'll develop it over years. You have it now.

For the right hiring manager, that's differentiated, not just developmental. You'll do best at companies that hire junior engineers with explicit plans to grow them — places where "can this person eventually lead a team or own a project" is part of the junior eval.

Now, the draft. Here's a full rewrite:

---

**TYLER BROOKS**
tyler.brooks.tx@gmail.com · (512) 555-0192 · Austin, TX · github.com/[yourusername]

---

**SUMMARY**

Marine infantry NCO transitioning to software engineering, with six years of experience designing training programs, leading teams, and solving problems under pressure. Developed curriculum for 300+ Marines annually, built new training programs from scratch, and achieved conversational Pashto fluency for an advising deployment to Afghanistan. Currently completing a B.S. in Computer Science while building full-stack skills in Python and JavaScript.

---

**TECHNICAL SKILLS**

Languages: Python, JavaScript, HTML/CSS
Frameworks & Tools: Flask, Git, Linux CLI
Foundations: REST APIs, responsive web design

---

**PROJECTS**

**Task Manager** | Python | github.com/[yourusername]/task-manager
Command-line task management application. Supports adding, completing, and listing tasks with persistent storage.

---

**EXPERIENCE**

**United States Marine Corps** | 2018–2024

*Training NCO — School of Infantry West, Camp Pendleton* | 2022–2024
- Designed and delivered lesson plans for a 12-week small-unit tactics course, training 300+ Marines per year across four cohorts
- Built three new training modules, expanding the program curriculum from initial design through instructor certification
- Led a four-person instructor section, managing scheduling, performance evaluation, and day-to-day operations

*Security Force Assistance Advisor — Kandahar, Afghanistan* | 2020–2022
- Advised Afghan National Army units on small-unit tactics, training, and operational planning
- Achieved conversational fluency in Pashto — a Category IV language — to communicate directly with local forces
- Worked across cultural and organizational boundaries to build trust and coordinate operations in a high-stakes environment

---

**EDUCATION**

Austin Community College — B.S. Computer Science, expected 2026 *(in progress)*
University of Texas at Austin — 60 credits completed, 2016–2018

Certifications: Python for Everybody (Coursera, 2024) · Responsive Web Design (freeCodeCamp, 2024)

---

**Three things to do before you send this:**

1. **Push the to-do app to GitHub** and write a README — what it does, how to run it, one sentence on what you learned. The README is a writing sample. Call it something slightly more polished than "todo-app" in the repo name.
2. **Add your GitHub URL** to the header — this is now a live document that proves you can ship code.
3. **Drop the UT Austin entry if it's hurting you** — 60 credits from 2016–2018 that you didn't finish might raise more questions than it answers for some recruiters. The ACC degree plus certifications is a cleaner story. Your call.

Does this feel like an accurate picture of you, or are there things here that don't ring true?

## Turn 4

**User:**
Yeah, this is substantially better. The bullets actually look like a resume now.

A couple reactions: the summary feels a little aggressive to me — "I've already done the hard parts of engineering leadership" is how you framed it, but I'd feel like I was overselling if I said that out loud. Is that line intended to stay word-for-word or is it more the underlying logic I'm selling?

On UT Austin — I'm actually still working toward the same degree at ACC, so dropping it might make the interrupted enrollment look worse. My plan is to finish there. I'd probably keep it.

The GitHub thing I'll do this week. Task manager's not that impressive but the README advice makes sense.

Honest question though: you said "for the right hiring manager." How do I identify which companies those are before I apply? Because right now I've been applying pretty broadly — whatever's on LinkedIn that says entry-level or junior — and I don't know how to filter for the ones where this pitch works.

**Assistant:**
Good catch on the summary — that line was the underlying logic for you to understand the *pitch*, not literal resume copy. What I actually wrote in the draft is already softer: "designing training programs, leading teams, and solving problems under pressure." That's defensible and specific. Keep that.

On UT Austin — your reasoning is sound. One small tweak to make the continuity clearer:

> Austin Community College — B.S. Computer Science, expected 2026 *(continuing coursework begun at UT Austin)*
> University of Texas at Austin — 60 credits completed, 2016–2018

That way it reads as a continuous path, not two abandoned attempts.

---

**On identifying the right companies:**

The "apply broadly to anything that says entry-level" strategy is almost certainly hurting your conversion rate. You're a non-traditional candidate — you need to find companies where non-traditional is an asset, not something to explain away.

Three concrete filters:

**1. Companies with veteran hiring programs.** Not charity — these companies have learned veterans perform. Amazon, Microsoft, Salesforce, Twilio, and many others have active programs. Google "company name veteran hiring" or look for a "military" page on their careers site. These programs often have more tolerance for unconventional technical backgrounds.

**2. Defense tech and govtech startups.** Your domain knowledge is genuine differentiating value here, not just a soft-skill story. Companies like Anduril, Shield AI, Rebellion Defense, and dozens of smaller Austin-area contractors actually *want* people who understand how the military operates. Your MOS and deployment experience reads completely differently to a hiring manager who's building products for warfighters.

**3. Series A/B startups (10–100 people) hiring for growth.** Job descriptions that say things like "mentorship," "we'll invest in your growth," "learning mindset," or describe a junior role with broad scope — these are companies hiring for potential, not credentials. A 15-person startup that needs a junior dev to also help document the API, train internal users, and eventually own a product area is exactly where your background compounds.

**Signals to avoid** (at this stage): job descriptions that are 80% required technologies with specific version numbers, no mention of mentorship or growth, or companies clearly looking for someone who can be productive from day one with minimal investment.

**One more channel worth pursuing:** the military-to-tech community. Veterans in tech talk to each other. A referral from a veteran who's now a software engineer is worth 20 cold applications. Look at Vet2Tech, VetsinTech, and the Hiring Our Heroes tech fellowship — and search LinkedIn for people with military backgrounds who are now engineers at companies you're targeting. A cold message that starts "I'm a fellow veteran transitioning into software engineering" gets opened.

The resume is now the stronger piece. The targeting is where the next leverage is.

## Turn 5

**User:**
The defense tech angle hadn't occurred to me and it's probably the most useful thing you've said. Anduril has an Austin office — I've seen their name before but assumed I wasn't technical enough. If my domain knowledge actually reads as an asset there rather than something I have to explain, that changes the math.

The veteran hiring programs I knew existed but wrote off as mostly military intelligence and logistics roles. Worth actually checking.

One thing I want to push back on slightly: the LinkedIn cold message strategy. I've tried two of those and got no response. Is the framing I'm using wrong, or is it just a low-hit-rate thing where I need to send 20 to get 2?

Also — "own a product area" is exactly the kind of phrase that makes me want to keep going with this. That's the part of engineering I'm actually trying to get to. How long does it typically take a junior dev to get to that kind of scope at one of those Series A companies?

**Assistant:**
Both — wrong framing *and* low hit rate — but framing is the bigger lever.

**On the cold messages:**

Two messages isn't a sample; you'd need 20-30 to know if your approach works. But the most common mistake is asking for too much. If your message is anything like "I'm interested in opportunities at [company] and would love to connect" — that's why you're not getting responses. People ignore asks that feel like work.

The version that gets replies:

> "Hi [Name] — I noticed you made the transition from [military/non-traditional background] to software engineering at [Company]. I'm doing something similar — six years in the Marines as an infantry NCO, now building my CS skills. Would you have 15 minutes sometime to talk about what that first year looked like? No ask beyond that."

Four sentences. Specific to them. Small ask. No pressure. The "no ask beyond that" line does real work — it signals you're not about to ask for a referral.

If you're targeting Anduril specifically, there's a sharper version: lead with the domain knowledge, not the transition story. "I spent six years as an infantry NCO including a Security Force Assistance deployment to Kandahar — I've been following Anduril's work and would love to talk to someone about what it's like building software there with that kind of background." That's a different conversation than "I'm a career changer."

---

**On the timeline:**

Honest answer: at a 15-30 person Series A company, 18–24 months to meaningful ownership is realistic for someone with your background — faster than average, because the non-technical half of that development (communication, stakeholder management, leading without authority) is already built. Most junior devs are still developing that at year three.

The catch is that the first 12 months will be mostly about proving technical execution. Shipping reliable code, understanding the codebase, building trust with senior engineers. Your leadership experience doesn't substitute for that — it sits on top of it. You have to earn the technical credibility before the soft skills become a visible asset.

The upside of a small company: there's no bureaucratic queue for ownership. If you're good and the company is growing, responsibilities expand because there's no one else to take them, not because you waited your turn.

---

Worth naming: we've drifted from resume help into job search strategy, which I think is the right conversation to be having. The resume was the symptom; the underlying question is how to make this transition work. Do you want to keep pulling on that thread — targeting, outreach, positioning — or is the resume the priority right now?

## Turn 6

**User:**
Keep pulling on the strategy thread. The resume's in better shape — that's done enough for now.

The 18-24 month timeline is honest and I can work with it. The part I'm sitting with is what you said about the first year: mostly proving technical execution, shipping reliable code. I understand why that's necessary. I'm just not sure it's the part I'm actually excited about.

The stuff you described as "already built" — stakeholder management, leading without authority — that's what I liked about the job I had. The coordination. Getting a 12-week course to run on time with four instructors who all had opinions. Getting Afghan commanders to trust a process they didn't design. That's where I was actually engaged. Writing code is fine, I can do it, but I don't think about it the way I think about that.

I guess I just assumed software engineering was the path because of the CS credits and the self-study work I've done. It seemed like the obvious next step. Is there something about the way I'm describing what I liked that changes how you'd think about where I should be targeting?

**Assistant:**
Yes, it changes things significantly. What you just described — coordination across stakeholders with different interests, earning trust in a process you didn't design, running a complex program with people who all had opinions — that's not the part of software engineering that gets you excited. That *is* the job of a Product Manager.

I want to name that clearly because I think it matters: you may be applying for the wrong role.

Software engineering is a path to the work you described, but it's indirect. You'd spend 2-3 years doing the part you're only "fine" with before the coordination and leadership work becomes a real part of the job. Product management gets you there immediately — that's the whole job from day one.

What a PM actually does, specifically:
- Figures out what to build and why, working with engineers, designers, customers, and leadership who all have different opinions
- Drives execution of something they didn't design and don't have authority to mandate
- Gets a team to trust a roadmap and commit to it
- Manages stakeholders across functions who don't report to them

That's a nearly literal description of what you said you were engaged by.

Your technical literacy — the CS coursework, the Python and JavaScript, understanding how software is built — makes you a *better* PM, not a less qualified one. You don't need to be a senior engineer to be an effective PM. You need to understand engineering well enough to work credibly alongside engineers, which you're building.

**Before I go further:** Did you consider PM roles and decide against them for a reason, or did you just not see them as an option? That changes what's useful to say next.

## Turn 7

**User:**
Wait — you can apply for that directly? I thought PM was something you got promoted into after you'd been an engineer for a while. Like a senior title. I didn't know it was a role you could come in at from outside engineering.

I haven't considered it at all. I didn't rule it out for a reason, it just never occurred to me as something I'd apply for. When I've seen "PM" I assumed it was out of reach for where I am.

If what you're describing is accurate — that the job from day one is the coordination and stakeholder work — then yeah, that's what I'm actually describing when I talk about what I liked. Getting disparate people aligned on a thing, driving it to completion, being accountable for the outcome. That's not something I'd have to grow into. That's been my job for years.

What does entry-level PM even look like? And would my background actually get me in the door, or is this one of those situations where the role requires an MBA or an existing product background?

**Assistant:**
Yes, you can apply for it directly. The "PM is a promotion from engineer" model exists at some companies, but it's not the norm and it's definitely not the only path.

**Associate Product Manager programs** exist specifically for this. Google, Microsoft, Uber, Lyft, Salesforce, Atlassian, and dozens of others run formal APM programs designed for people entering PM from outside. No engineering background required. No MBA required. They explicitly recruit from military, consulting, and non-traditional paths because those backgrounds produce people who can lead without authority — which is the hardest part of the job and the part you can't teach in six months.

At startups, entry-level PM is even more accessible. A 20-person company with one PM and a growing product needs someone who can own it — write the specs, talk to customers, drive the engineering team to a decision, ship the thing. They're not looking for credentials, they're looking for someone who's done that kind of work.

**Would your background get you in the door?** For most of these paths, yes — and in some cases you'd be a strong candidate, not just a passable one.

What they're evaluating for PM: communication, analytical thinking, leading without authority, user empathy, and understanding how software gets built. You have the first three demonstrably. The technical literacy you're building covers the last one. User empathy you'd need to make the case for — but "I had to earn trust from Afghan commanders who didn't design the process I was asking them to follow" is actually a credible answer to "tell me about understanding your user."

The interview process is completely different from SWE — no LeetCode. Instead: product design questions ("design a feature for X"), metrics questions ("how would you measure success"), and behavioral questions where your military experience is a direct asset. You'd need to learn some PM vocabulary and frameworks, but that's weeks of prep, not months.

**Your strongest angle right now:** PM roles at defense tech companies. Your domain knowledge isn't just a soft-skill story there — it's genuine subject-matter expertise that makes you better at the job from day one.

**Practical question:** Do you want to pivot your applications toward PM, run both tracks in parallel, or figure out which first? Because the resume we wrote today is still mostly right — the accomplishments are the same — but the framing shifts.

## Turn 8

**User:**
This is the most useful thing anyone's said to me since I started this process.

I didn't know APM programs existed. That changes the calculus significantly. If there's a formal path in that doesn't require five years of engineering experience, I want to know more about it.

On the decision — I don't think I want to run both tracks. That feels like trying to tell two different stories and doing both poorly. If PM is actually a better fit for what I want to be doing in three years, I should commit to it. What I'm not sure about is how confident I should be in that assessment after a fifteen-minute conversation. Is there a way to pressure-test it before I start redoing everything?

And practically: how much does the resume shift? The accomplishments are the same but you said the framing changes. What's different about how a PM resume tells that story versus what we put together today?

**Assistant:**
Good instinct on the single track. Split focus at this stage of a job search compounds the problems.

**On pressure-testing it:**

Fifteen minutes is enough to identify a hypothesis, not enough to commit. Here's how to validate it cheaply before redoing anything:

**Talk to two or three actual PMs.** Not to ask for a job — ask what their week looks like. What's the part that drains them? What surprised them coming in? If the honest description still sounds like work you want, you have your answer. Target PMs at small companies or defense tech where the coordination-to-bureaucracy ratio is high. This takes a week, not a month.

**Read five PM job descriptions carefully.** Not the qualifications — the responsibilities section. Does it sound like the job you want to have, or does it sound like someone else's job?

**Do one product design question.** These are standard PM interview questions: "Design a feature that helps veterans transition into the workforce" or "How would you prioritize the roadmap for a training software product?" If that kind of thinking energizes you, that's signal. Google "PM interview product design questions" and spend an hour with one. Your reaction tells you something.

The asymmetry here matters: the cost of spending a week validating is low. The cost of another 10 weeks applying for the wrong role is high.

---

**On how the resume shifts:**

Same accomplishments, different lens. PM resumes emphasize outcomes, decisions, and cross-functional coordination. SWE resumes emphasize tools and what you built. Here's the diff on the bullets that change most:

*Today's version (SWE framing):*
> Designed and delivered lesson plans for a 12-week small-unit tactics course, training 300+ Marines per year

*PM framing:*
> Defined requirements, developed curriculum, and launched a 12-week training program serving 300+ Marines annually — iterating on content based on cohort performance

"Defined requirements, developed, launched, iterated" is PM vocabulary for discovery → spec → delivery → learning. That's not spin; that's what you actually did, named correctly.

*Today's version:*
> Built three new training modules, expanding the program curriculum from initial design through instructor certification

*PM framing:*
> Identified gaps in existing curriculum, scoped and built three new training modules, and drove adoption through instructor certification — expanding program coverage without adding headcount

"Identified gaps, scoped, drove adoption" — that's a product launch story.

*The Afghanistan bullet stays almost the same* — but add one word:
> Earned trust of Afghan National Army commanders for operational processes they didn't design, enabling sustained collaboration across significant cultural and organizational barriers

"Earned trust for a process they didn't design" is exactly how PM describes stakeholder adoption.

**Summary rewrite for PM:**
> Marine infantry NCO transitioning to product management with six years of experience driving complex programs, aligning stakeholders across organizational boundaries, and delivering outcomes under pressure. Built and launched training programs from scratch; earned cross-cultural trust in high-stakes environments. Technically literate — completing B.S. in Computer Science — with hands-on experience in Python and JavaScript.

**What changes structurally:** The GitHub project matters less. Technical skills stay (PM roles value technical literacy) but move lower. If you have any data on outcomes — pass rates, curriculum adoption, anything — those go in now.

---

**The practical sequence I'd suggest:**

1. This week: have one real conversation with a PM (LinkedIn, veteran network, anyone)
2. Do one product design question cold and notice your reaction
3. If both feel right: reframe the resume, start researching APM programs and defense tech PM openings
4. If something feels off: come back and interrogate it

You're not throwing away the last few months. The Pashto story, the 300 Marines, the three modules — those work for PM at least as well as they work for SWE. Probably better.

## Turn 9

**User:**
The reframed bullets are better. "Defined requirements, developed, launched, iterated" — I can see exactly what that's doing and it doesn't feel like spin. That's what I actually did, named in a way that's legible to the right audience.

The validation sequence makes sense. Talking to a PM first is the right move before I redo anything. I can find someone through the veteran network or LinkedIn using the approach you gave me earlier.

I came in thinking I needed better action verbs. I'm leaving with a different resume, a different job target, and a week of specific homework. That's a better outcome than I expected.

I think I have what I need for now. Thanks.

**Assistant:**
Good luck with it. The homework is concrete and the path forward is clear — that's usually the hard part.

When you've talked to a PM and done a product design question, come back if you want to think through the resume rewrite or how to approach APM applications. The Pashto story alone is going to make people sit up straight.
