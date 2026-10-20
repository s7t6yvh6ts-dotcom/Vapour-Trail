# Chainline Cycles: order confirmation email

This is the email every customer gets once their bike order is accepted. Send it for **every online, phone or email order**, whether they collect the bike or have it delivered. Shopify's standard order email and Stripe's receipt leave out the cancellation rights, the cancellation form and the warranty, so on their own they aren't enough.

## Why it's needed (the law, briefly)

- **Consumer Contracts Regulations 2013 (CCR), regulation 16.** After a distance sale you must confirm the contract on a *durable medium* (an email or a PDF counts; a web page doesn't), within a reasonable time and no later than when the bike is delivered or collected. It must carry the Schedule 2 information unless you've already given it on a durable medium: who you are and your geographic address, the bike and its main characteristics, the total price including delivery, payment and delivery arrangements, the 14-day cancellation right and how to use it, **who pays to return the bike** (a bike can't normally be posted, so the cost must be stated), the legal guarantee, the warranty, and complaints.
- **Regulation 13(1)(b) and Schedule 3, Part B.** The model cancellation form must be given or made available. The site has it in its small print (`#cancel-form`); this email repeats it word for word, so the customer keeps a copy.
- **Regulation 31.** If the cancellation information isn't given properly, the 14-day period runs on for up to 12 months.
- **Regulation 34.** Refunds within 14 days of getting the bike back, or of the customer's proof of sending it, whichever is sooner, to the original payment method.
- **Consumer Rights Act 2015, section 30.** The warranty must be in plain language and give the guarantor's name and address, how to claim, how long it lasts and where it applies. On request it must be in writing, so an in-person sale gets it on the printed receipt (see the end).

The site's legal text was checked against legislation.gov.uk and gov.uk search extracts in the 14 October 2026 legal audit; the same wording is used here.

## How to use it

| Checkout | What to send |
|---|---|
| **Shopify** (recommended, GO-LIVE.md section 5) | Two emails. (1) Paste `order-confirmation-email.html` into **Settings > Notifications > Order confirmation** (Edit code, replacing the whole template). Shopify sends it straight after checkout, so the customer has every right on a durable medium before the contract is made. (2) Within [one working day] of payment, send the email below with the bike's details filled in. Terms clause 3 says the contract is made "when we email to confirm we've accepted your order", so this email is the acceptance. |
| **Stripe Payment Links, or a phone or email order** | Send the email below, filled in, within [one working day] of payment and before the bike is delivered or collected. It's the acceptance and the confirmation in one. |

Send it from the workshop inbox and keep a copy with the bike's ticket for six years (the privacy notice says sales records are kept that long).

Before launch, put one test order through and read both emails on a phone and on a computer. Check every [placeholder] is filled and every line is still true of the bike.

**Two kinds of brackets.** `[Company name]` and the other bracketed business details are the same placeholders as on the site (GO-LIVE.md section 3): fill them once, with the same values. `{Order number}` and the other curly-brace fields are filled for each order. In the cancellation form, the customer fills in `[bike, size, ticket number]`, `[date]`, `[your name]` and `[your address]`, exactly as on the site. Leave those as they are.

**Your call before the first one: the frame number.** The line below gives the full frame number, so the buyer can check it against the bike and register it on BikeRegister in their own name. Nothing on the site promises to keep it out of emails. If you'd rather not send it, delete that line (and the BikeRegister registration offer). Either way, the frame number is never published on the website.

---

**Subject:** Your Chainline Cycles order {Order number}: confirmed

Hi {Customer first name},

Thank you for your order. This email confirms we've accepted it, so our contract is now made. Please keep this email: it has your bike's details, your right to cancel and a cancellation form, your warranty, and how to reach us.

### Your bike

- **Order number:** {Order number}
- **Order date:** {Order date}
- **Bike:** {Make} {Model}, {Year}, size {Size}
- **Workshop ticket:** {Ticket number}. The full ticket comes with the bike.
- **Frame number:** {Frame number}. It wasn't listed as stolen on BikeRegister when we checked on {BikeRegister check date}. [If you offer it: We can register the bike to you on BikeRegister; reply to say yes.]
- **30-point workshop check:** passed on {check date}.
- **Work done:** {from the ticket: what we fitted, replaced or tested}
- **Condition:** {the condition notes from the listing}

**E-bikes only** (delete for a pedal bike):

- **Motor:** {motor maker}, {rated power}W (250W or less). Assistance cuts out at 15.5 mph, and we checked the maker's plate.
- **Battery:** {rated Wh} Wh rated. Battery health {x}%: our capacity test measured {x}% of the battery's rated capacity on {test date} ({test method}). Range also depends on the rider, the route, the weather and the assist level, so it isn't a range promise.
- **Charger:** the maker's own, included.
- Riders must be 14 or over.

### Price and payment

- **Total paid:** £{Total}. Prices are in pounds sterling and include VAT where applicable. Used bikes may be sold under the VAT margin scheme, in which case VAT isn't shown separately on your receipt.
- **Collection or delivery:** {Free collection from the workshop} *or* {UK delivery, £39} *or* {E-bike courier, £[e-bike delivery price]}. It's included in the total above.
- **Paid by:** {Payment method, e.g. card through Shopify Payments}. We never see or store your card details.

### Collection or delivery

*Use the paragraph that fits and delete the other.*

**Collecting:** your bike will be ready at [Workshop address], open [Opening hours]. We'll email or phone you when it's ready, usually within [2] working days. Bring this email, and we'll set the saddle height with you.

**Delivery:** your bike goes to:

{Delivery address}

We send it within [3] working days of this email, and it usually arrives [2 to 3] working days later; we always deliver within 30 days unless we agree otherwise with you. {Courier name} will bring it{, a specialist courier, because Royal Mail and Parcelforce don't carry e-bikes}. It's boxed 90% built: you fit the pedals and turn the bars straight, and the tools you need are in the box. The bike is our responsibility until it's delivered to you. If it arrives damaged, or hasn't arrived when expected, email [Workshop email] or phone [Phone number] and we'll put it right.

**Free check-up:** new cables stretch as they bed in. Bring the bike back within [8] weeks and we'll re-adjust the gears and brakes, labour free.

### Your right to cancel: 14 days, any reason

Under the Consumer Contracts Regulations 2013, because you ordered online, by phone or by email, you can cancel for any reason within 14 days, starting the day after you get the bike, whether we delivered it or you collected it.

- **How to cancel:** tell us clearly by email to [Workshop email], by phone on [Phone number], or by post to [Company name], [Workshop address]. You can use the cancellation form below, but you don't have to; any clear statement is fine.
- **Returning the bike:** a bike is too big to post, so returning it is at your cost. Bring it back to the workshop, or we'll collect it for £39 (e-bikes £[e-bike collection price]), or use your own courier. Please do it within 14 days of telling us.
- **Your refund:** we refund the price of the bike and the delivery charge you paid, to your original payment method, within 14 days of getting the bike back, or of you showing us you've sent it, if that's sooner.
- **Handling:** treat it as you would in a shop: check it over, set the saddle and take it for a short test ride. If it comes back ridden more than that, or with damage that wasn't there when you got it, we may take the loss in value off your refund, as the law allows. We'll show you before we do.

### Cancellation form

You don't have to use this form; any clear statement by email is fine. If you prefer, copy it into an email or letter:

> To [Company name] trading as Chainline Cycles, [Workshop address], [Workshop email]:
> I hereby give notice that I cancel my contract of sale of the following goods: [bike, size, ticket number]
> Ordered on [date] / received on [date]
> Name: [your name]
> Address: [your address]
> Signature (only if sent on paper):
> Date: [date]

### Your 3-month warranty

This warranty is given by [Company name], trading as Chainline Cycles, [Workshop address] ([Workshop email], [Phone number]). It covers bikes bought from us, applies in the UK, and lasts for 3 months from the day you collect the bike or it's delivered. It's on top of your Consumer Rights Act 2015 rights, not instead of them.

- **Covered:** the whole bike, parts and labour. If any part stops working properly with normal use within the 3 months, we put it right free. On an e-bike that includes the motor, display, wiring, battery and charger.
- **Not covered:** crash damage, punctures, and normal wear on tyres and brake pads; damage from misuse; loss or theft. We'll tell you straight if a problem is one of these, and quote before we do any paid work.
- **How to claim:** email or phone us with your ticket number ({Ticket number}) and what's wrong; photos help. Bring the bike to the workshop if you can. If you can't, tell us: for a fault we're responsible for under the Consumer Rights Act (any fault reported within six months of getting the bike is presumed to be), we pay to collect the bike and bring it back. For other warranty claims, [who pays to collect and return the bike, and what it costs]. We put a covered fault right free of charge.
- **This warranty is extra**, and it never limits your Consumer Rights Act rights: within 30 days of getting the bike you can reject it for a full refund, and after that you're entitled to a repair or replacement, and if that doesn't fix the problem, a price reduction or refund.

### Your legal rights come first

This warranty doesn't reduce your Consumer Rights Act 2015 rights. A used bike must still be of satisfactory quality (taking into account its age, condition and price), fit for purpose and as described. Within 30 days of getting it, you can reject a faulty bike for a full refund. After 30 days, we get one chance to repair or replace it. If that doesn't fix it, you can reject it for a refund (which, after six months, may be reduced to reflect the use you've had) or keep it with a price reduction. Within six months of getting it, a fault is assumed to have been there when you got it unless we can show otherwise. You can make a claim for up to six years after delivery (five years in Scotland).

### E-bike battery safety (e-bikes only)

Use only the maker's charger that came with the bike. Don't charge a battery that's damaged, swollen or has been under water: bring it to us instead. Charge it somewhere you'd notice a problem, not while you're asleep or out.

### If you're unhappy

Please tell us first, by email to [Workshop email] or phone on [Phone number], and we'll do our best to put it right. You can also get free advice from the Citizens Advice consumer helpline on 0808 223 1133.

### Our terms and our details

Your order is under our terms of sale as they stood on {Order date}: {link to that version of the terms, or attach it as a PDF}.

Chainline Cycles is a trading name of [Company name], a company registered in [England and Wales], company number [Company number], registered office [Registered office address]. Workshop: [Workshop address]. VAT number: [VAT number, if registered]. Email [Workshop email], phone [Phone number].

---

**Keeping the terms "as at the order date".** The terms live in the page's small print, which shows whatever it says today. Each time you change them, save the small print as a PDF named with its "Last updated" date (for example `chainline-terms-2026-11-02.pdf`) and keep every version. Attach the current one to this email, or host it and link that file. Never edit a version once you've sent it.

**Sole trader?** Use "Chainline Cycles is run by [your name], [Workshop address]." and delete the company clauses, as on the site (GO-LIVE.md section 3).

**Not VAT-registered?** Delete the VAT number sentence, as on the site.

**Bikes sold in person at the workshop** have no 14-day cancellation right (only distance and off-premises sales do), but every Consumer Rights Act right applies, and the warranty must be given in writing on request. Give a printed receipt with the bike, ticket number, frame number, price, the "Your 3-month warranty" and "Your legal rights come first" sections above, and the trader details.
