# Full Bars: order confirmation email

This is the email every customer gets once their order is accepted. Send it for **every order**, on either checkout. Stripe's receipt and Shopify's standard order confirmation leave out the cancellation rights, the cancellation form and the guarantee and warranty terms, so on their own they aren't enough.

## Why it's needed (the law, briefly)

- **Consumer Contracts Regulations 2013, regulation 16.** After a distance sale you must confirm the contract on a *durable medium* (an email or a PDF counts; a web page doesn't). It must reach the customer within a reasonable time, and in any case no later than delivery. It must contain the Schedule 2 information (who you are, your geographic address, the goods, the total price, payment and delivery arrangements, the cancellation right and how to use it, who pays return postage, the legal guarantee, any after-sales guarantee, complaints), unless you've already given that information on a durable medium before the contract was made.
- **Regulation 13(1)(b)** requires the model cancellation form (Schedule 3, Part B) to be given or made available before the contract is made. The site has it on `delivery-returns.html`; this email repeats it so the customer has a copy they keep.
- **Regulation 31.** If the cancellation information isn't given properly, the 14-day cancellation period is extended by up to 12 months. If you give it late, within those 12 months, the period ends 14 days after the customer receives it.
- **Regulation 34.** Refunds within 14 days of getting the goods back, or of the customer's proof of sending them, if that's earlier. This email repeats the site's promise, which already meets that.

I checked these through search extracts of legislation.gov.uk, because the site itself is blocked from my sandbox. Regulation 36 deals with services, not goods, so it doesn't apply to phones.

## How to use it

| Checkout | What to send |
|---|---|
| **Static site (email orders and Stripe Buy now)** | Send the email below, filled in, within 1 working day of payment and before the phone is dispatched. Terms section 3 says the contract is made "when we email to confirm your order has been accepted", so this email is the acceptance and the confirmation together. Send it from `hello@fullbars.co.uk`. Keep a copy. |
| **Shopify** | Two emails. (1) Paste `order-confirmation-email.html` into **Settings > Notifications > Order confirmation**. Shopify sends it straight after checkout, so the customer has every right on a durable medium before the contract is made. Shopify doesn't know which unit they'll get, so that email says the exact phone details follow. (2) Within 1 working day of payment, send the email below with the unit's details filled in. That is the acceptance, as on the static route. A phone with a replaced part, sold by a draft order invoice (GO-LIVE.md section 4), gets both emails too: name the replaced part in the custom item's title and in the Parts line below. |

Before launch, put one test order through on the route you chose and read both emails on a phone and on a computer. Check every [placeholder] is filled and every line is still true.

**Two kinds of brackets.** `[Company name]` and the other bracketed business details are the same placeholders as on the site (GO-LIVE.md section 3). Fill them once, with the same values. `{Order number}` and the other curly-brace fields are filled for each order. In the cancellation form, the customer fills in `[phone, storage, grade, colour]`, `[date]`, `[your name]` and `[your address]`, exactly as on `delivery-returns.html`. Leave those as they are.

**Decide before you send the first one (your call). This decision covers both files.** `delivery-returns.html` says each phone's identifier "never appears on our website, emails or receipts". The IMEI line below shows only the last 4 digits, which lets the customer check they got the phone you described. Either change that sentence on `delivery-returns.html` first (suggested: "only its last 4 digits appear in your order confirmation, so you can check it's the phone we described; the full number never appears on our website, emails or receipts"), or delete the IMEI line below. Don't send both as they are. The Shopify template, `order-confirmation-email.html`, doesn't mention the IMEI at all, so it's safe either way. If you change the site sentence, you can also add the IMEI ending to its second paragraph (its header comment, item 4, says where).

---

**Subject:** Your Full Bars order {Order number}: confirmed

Hi {Customer first name},

Thank you for your order. This email confirms we've accepted it, so our contract is now made. Please keep this email: it has your phone's details, your right to cancel and a cancellation form, your guarantee and warranty, and how to reach us.

### Your phone

- **Order number:** {Order number}
- **Order date:** {Order date}
- **Phone:** {Model}, {Storage}, {Grade} grade, {Colour}
- **IMEI ending:** {last 4 digits} (see the note above before you use this line)
- **Battery health:** {Battery health}% of its original capacity (at least 90% for Excellent, 88% for Very Good, 85% for Good)
- **Parts:** {All original manufacturer parts.} *or* {Replaced part: {which part}, {a genuine Apple / Samsung / Google part, or not}.}
- **Grade:** {Grade}, as described in our published grading standard: https://www.fullbars.co.uk/grading.html

### Price and payment

- **Total paid:** £{Total}. Prices are in pounds sterling and include VAT where applicable. Second-hand phones may be sold under the VAT margin scheme, in which case VAT is not shown separately on your receipt.
- **Delivery:** free within the UK, so the price above is the total you pay.
- **Paid by:** {Payment method, e.g. card through Stripe}. We never see or store your card details.

### Delivery

Your phone goes by Royal Mail Special Delivery or an equivalent tracked, insured, signed-for service, to:

{Delivery address}

Orders paid before 2pm on a working day are dispatched the same day, subject to our security checks; we may review a first order by hand before it ships. That usually means it arrives the next working day. We'll email you the tracking reference when your phone ships. The phone is our responsibility until it's delivered to you. If it hasn't arrived when expected, or arrives damaged, email hello@fullbars.co.uk and we'll sort it out.

### Your right to cancel: 14 days, any reason

Under the Consumer Contracts Regulations 2013 you can cancel for any reason within 14 days, starting the day after your phone is delivered.

- **How to cancel:** tell us clearly by email to hello@fullbars.co.uk, or by post to [Company name], [Registered business address]. You can use the cancellation form below, but you don't have to; any clear statement is fine.
- **Sending it back:** we send you a free, tracked returns label, so you don't pay to return it. Post the phone back within 14 days of telling us, with the cable and SIM tool, well packed. Back up the phone, sign out of your accounts and reset it before sending it.
- **Your refund:** we refund the full amount, including the original delivery cost, to your original payment method within 14 days of receiving the phone back, or of you showing us proof you've sent it, if that's earlier (usually the same day).
- **Handling:** use it like you'd use it in a shop: switch it on, look at it, check it's what you wanted. If it comes back with a new crack or a dent that wasn't there when we sent it, we may deduct for that, as the law allows. We'll show you before we do.

### Cancellation form

You don't have to use this form; any clear statement by email is fine. If you prefer, copy it into an email or letter:

> To [Company name] trading as Full Bars, [Registered business address], hello@fullbars.co.uk:
> I hereby give notice that I cancel my contract of sale of the following goods: [phone, storage, grade, colour]
> Ordered on [date] / received on [date]
> Name: [your name]
> Address: [your address]
> Signature (only if sent on paper):
> Date: [date]

### Our 30-day satisfaction guarantee

On top of that, if you're not happy with your phone for any reason within 30 days of delivery, send it back for a full refund or an exchange. Same prepaid label, same refund timescale.

### Your 12-month warranty

This warranty is given by [Company name], trading as Full Bars, [Registered business address] (email hello@fullbars.co.uk). It covers phones bought from us, applies in the UK, and lasts for 12 months from the day your phone is delivered. It is on top of your Consumer Rights Act 2015 rights, not instead of them.

- **Covered:** any function that stops working properly within 12 months and isn't down to damage, liquid or a repair by someone else; the battery, if its health drops below 80% within 12 months; any part we have replaced; the charging cable supplied with your phone.
- **Not covered:** physical damage (drops, cracks and dents), liquid damage, anything opened or repaired by someone other than us, software problems, normal wear to the outside and consumables such as screen protectors, loss or theft.
- **To claim:** email hello@fullbars.co.uk with your order reference and what's wrong. We reply within one working day. We repair it first. If we can't, we replace it with the same or better. If we can't do that, we refund you.
- Full details: https://www.fullbars.co.uk/warranty.html

### Your legal rights come first

Under the Consumer Rights Act 2015 your phone must be of satisfactory quality (taking into account its age, grade and price), fit for purpose and as described. Within 30 days of delivery you can reject a faulty phone for a full refund. After 30 days we get one chance to repair or replace it; if that doesn't fix it, you can reject it for a refund (which, after six months, may be reduced to reflect the use you've had) or keep it with a price reduction. Within six months of delivery a fault is assumed to have been there when it arrived unless we can show otherwise. Our guarantee and warranty are on top of these rights, not instead of them.

### If you're unhappy

Please email us first at hello@fullbars.co.uk (or phone [Phone number]) and we'll do our best to put it right. You can also get free advice from the Citizens Advice consumer helpline on 0808 223 1133.

### Our terms and our details

Your order is under our terms and conditions of sale as they stood on {Order date}: {link to that version of the terms, or attach it as a PDF}.

Full Bars is a trading name of [Company name], a company [registered in England and Wales], company number [Company number], registered office [Registered business address]. VAT number: [VAT number, if registered]. Email hello@fullbars.co.uk, phone [Phone number].

---

**Keeping the terms "as at the order date".** A link to `terms.html` shows whatever the page says today. Each time you change the terms, save the page as a PDF named with its "Last updated" date (for example `full-bars-terms-2026-10-20.pdf`) and keep every version. Attach the current one to this email, or host it and link that file. Never edit a version once you've sent it.

**Sole trader?** Use your own name for [Company name] and delete "a company [registered in England and Wales], company number [Company number]," as on the site (GO-LIVE.md section 3).

**Not VAT-registered?** Delete the VAT number sentence, as on the site.
