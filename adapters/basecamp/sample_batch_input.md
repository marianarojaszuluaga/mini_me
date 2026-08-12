# G-magine Batch Input
Generated: 20260318_171222


## INPUT FROM CARD: %Ticket% SSP First Contract – Sales & Ops Feedback (Issues + Improvements)
> Hi Team! 
SSP First Contract – Sales &amp; Ops Feedback (Issues + Improvements)
Sharing feedback collected from the first SSP contract execution highlighting usability issues, technical bugs, and process improvements across Sales and Ops. Several blockers affected client experience and required manual intervention.
Sales Feedback
1. Platform Invitation Failure: “Send Platform Invite Link” did not work.

2. Mobile Experience Issues

Client was unable to complete the process from their phone; screens would freeze, the FB CASH CAP investment page will not open, hard to read, etc.&nbsp;
This prevented progress entirely on mobile.
3. Data Persistence Issue
When re-entering from mobile, the system required re-uploading documents.
Other data fields remained saved.

Request: Enable document saving in draft version.
4. UX / Client Experience
Flow is intuitive for internal users assisting clients.
However, client stated they would not have been able to complete the process without assistance. - will request more feedback on this but not relevant for this version.&nbsp;

5. Opportunity Owner: all opportunities are being created under Fernando Cano's name:Opportunities should be created under the related Account Owner's Name, they should match: Account Owner = Opportunity Owner&nbsp;

6. Timing: Total process duration: ~1 hour 30 minutes.


Ops Feedback1. KYC / Sumsub Integration
Connect updated correct flow: “Full KYC - Onboarding”

Issue: “AML Check” field in Salesforce does NOT update automatically after KYC approval in sumsub. This blocks process progression until Ops manually updates it.

Fix needed: Automate AML field update post-KYC approval, and make sure that the KYC process is properly opened for new users.&nbsp;
2. Bank Account Information Issues
CLABE is missing in contract (only account number appears).
CLABE is also missing in Salesforce “Preview” view for approval.
In SSP Flow (user-facing UX):
Remove “CLABE” reference from account number field.
Keep CLABE as a separate required field (since it is mandatory for contract approval).



Reported case: User entered CLABE, but it did NOT populate in Salesforce, contract, or any record.
3. NotificationsNotifications to Tania are not active.

---

## INPUT FROM CARD: %Ticket% UX Proposal: Metrics Tooltips (AROI, ROI, MOIC, IRR)
> Hi team: proposal to improve clarity on investment metrics.



Goal: Help users understand the difference between AROI, ROI, Multiple, and IRR.


Scope:&nbsp;
Add info bubbles/tooltips next to each metric
Short, simple explanations (non-technical)
Goal is better understanding without cluttering the UI.

---

## INPUT FROM CARD: %Ticket% UX Request: Display Maturity Date (PNs)
> Hi team, opening this as a UX/UI proposal, coming from team feedback

Context: We already have a maturity date field for Promissory Notes (PNs), but it’s not clearly surfaced to users.

Goal: Improve visibility by displaying this as a “Expected Closing Date” within the Investments (Portfolio) view. (we may need a bubble or disclaimer here, working with Pepe on it, since this is always expected not guaranteed.&nbsp;


Scope (Phase 1)
Apply only to Promissory Notes (PNs)

Future: replicate for Deals - we are internally currently working on defining effective and maturity dates for deals, as they do not work exactly like with promissory notes.&nbsp;
Ask
Propose how/where to show “Expected Closing Date” in the portfolio view
Keep it clear and easy to understand for users
Goal is to align on UX before implementation.


---

## INPUT FROM CARD: %Ticket% QA Review: Password Reset Loop & Invite Link Flow Failure
> Hi team, flagging two related issues affecting client and internal user access. Requesting QA review + root cause analysis.



1. Password Reset Loop
Users (clients + internal) are being asked to reset passwords multiple times.

2. Invite Link Issue
“Send Platform Invite Link” is not letting some clients complete access → accounts are being activated manually. Reported they cannot move forward in the process after the first page, sometimes it takes them back to the login page without creating the account.&nbsp;


Ask
QA review both flows (login + invite)
Identify root cause(s)
Confirm if bug vs config issue



---

## INPUT FROM CARD: %Ticket% UX/UI + product definition ticket
> Hi team, opening this as a UX/UI + product definition ticket.


Context: Currently, clients have little to no visibility into upcoming distributions. This creates uncertainty, as they don’t know when to expect incoming transactions.

Problem: Upcoming distributions are not being clearly communicated or surfaced in the platform, leaving clients “blind” to what’s coming next.

Goal: Design a solution that makes upcoming distributions visible and understandable for clients, improving transparency and overall experience.

Scope (Exploration + Proposal Needed)
We are not defining the solution yet — the goal is for the team to propose the best approach.


The solution should consider:
Visibility within the platform (UX/UI)
Proactive communication (notifications, push, email, etc.)
Clear indication of timing, status, and type of transaction
Key Considerations / Constraints
Scope is limited to Distributions only (for now)
We need to align with Ops &amp; Finance on:
What data is available today
Whether upcoming distributions can be predicted vs manually defined


The solution may involve a mix of:
System-generated data
Manual inputs (if needed)



Key Questions to Address&nbsp;(Will set up call with Ops/Finance/CX)
How should “upcoming” be defined (timeframe, certainty level)?
How do we handle uncertainty (estimated vs confirmed distributions)?
Where should this be surfaced in the user journey?
What’s the right balance between visibility (UI) and proactive alerts?

Deliverable
Propose 1–2 solution approaches (flows or low-fidelity mockups are fine. The goal is to align on direction before moving into implementation.


Let me know thoughts.

---

## INPUT FROM CARD: %Ticket% Transactions View on Deals
> Hi Mar, We still cannot see the transactions object on the "Related" Page of Deals, we want to standardize this view on transactions for all opportunity types as we did with PN and Services.&nbsp;
    
  
    Screenshot 2026-03-17 at 12.16.39 PM.png
  



---

## INPUT FROM CARD: %Ticket% Bank Address on SSP Flow
> Hi team — the Sales team asked if we can add a dropdown field in the Bank Account section of the SSP/Platform.

When a bank is selected, its address should auto-populate using the attached catalog of common banks. We should also include an “Other” option for cases not covered in the list.


Goal: reduce input errors and standardize bank address data.Let me know feasibility and estimated effort.
    
  
    Screenshot 2026-03-17 at 12.09.13 PM.png
  


---

## INPUT FROM CARD: %Ticket% Graph on Client Portfolio Page
> Hi Team, this graph is still not easy to understand. int he example the color labels are General Real Estate, while the bars are labeled as undefined and there is no data for any other products. What's the progress on this? I know we were reviewing it.&nbsp;
    
  
    Screenshot 2026-02-19 at 6.36.20 PM.png
  



---

## INPUT FROM CARD: %Ticket% Login Page Edits
> 

  
  
    Maria
  
&nbsp; 
  
  
    Alejandro
  
&nbsp;
 Hi Team, Pepe shared the following edits for the login page&nbsp;



Remove the line: "Exclusive U.S. opportunities for LATAM."
Since we are using the field "Last Name" for both last names, he wants to label it properly in plural as: "Last Names" "Apellidos" as well as adding the bubble we talked regarding the explicit request for the name to match their legal documents&nbsp;



    
  
    Screenshot 2026-02-19 at 9.44.02 AM.png
  