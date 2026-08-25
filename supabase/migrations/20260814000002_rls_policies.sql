-- Row Level Security Policies

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE bills ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE item_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE settlements ENABLE ROW LEVEL SECURITY;

-- Profiles: users can read/update their own profile
CREATE POLICY "Users can view own profile"
    ON profiles FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile"
    ON profiles FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own profile"
    ON profiles FOR UPDATE
    USING (auth.uid() = user_id);

-- Bills: owners can CRUD; guest bills (null user_id) accessible via session_id (handled server-side)
CREATE POLICY "Users can view own bills"
    ON bills FOR SELECT
    USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can insert bills"
    ON bills FOR INSERT
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can update own bills"
    ON bills FOR UPDATE
    USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can delete own bills"
    ON bills FOR DELETE
    USING (auth.uid() = user_id);

-- Bill items: via bill ownership
CREATE POLICY "Users can view bill items"
    ON bill_items FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = bill_items.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

CREATE POLICY "Users can manage bill items"
    ON bill_items FOR ALL
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = bill_items.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

-- Participants
CREATE POLICY "Users can view participants"
    ON participants FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = participants.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

CREATE POLICY "Users can manage participants"
    ON participants FOR ALL
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = participants.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

-- Item allocations
CREATE POLICY "Users can view allocations"
    ON item_allocations FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM bill_items bi
        JOIN bills b ON b.id = bi.bill_id
        WHERE bi.id = item_allocations.bill_item_id
        AND (b.user_id = auth.uid() OR b.user_id IS NULL)
    ));

CREATE POLICY "Users can manage allocations"
    ON item_allocations FOR ALL
    USING (EXISTS (
        SELECT 1 FROM bill_items bi
        JOIN bills b ON b.id = bi.bill_id
        WHERE bi.id = item_allocations.bill_item_id
        AND (b.user_id = auth.uid() OR b.user_id IS NULL)
    ));

-- Bill adjustments
CREATE POLICY "Users can view adjustments"
    ON bill_adjustments FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = bill_adjustments.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

CREATE POLICY "Users can manage adjustments"
    ON bill_adjustments FOR ALL
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = bill_adjustments.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

-- Payment credits
CREATE POLICY "Users can view credits"
    ON payment_credits FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = payment_credits.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

CREATE POLICY "Users can manage credits"
    ON payment_credits FOR ALL
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = payment_credits.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

-- Settlements
CREATE POLICY "Users can view settlements"
    ON settlements FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = settlements.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

CREATE POLICY "Users can manage settlements"
    ON settlements FOR ALL
    USING (EXISTS (
        SELECT 1 FROM bills WHERE bills.id = settlements.bill_id
        AND (bills.user_id = auth.uid() OR bills.user_id IS NULL)
    ));

-- Storage bucket for bill images
INSERT INTO storage.buckets (id, name, public)
VALUES ('bill-images', 'bill-images', false)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Users can upload bill images"
    ON storage.objects FOR INSERT
    WITH CHECK (
        bucket_id = 'bill-images'
        AND auth.uid() IS NOT NULL
    );

CREATE POLICY "Users can view own bill images"
    ON storage.objects FOR SELECT
    USING (
        bucket_id = 'bill-images'
        AND auth.uid() IS NOT NULL
    );

CREATE POLICY "Users can delete own bill images"
    ON storage.objects FOR DELETE
    USING (
        bucket_id = 'bill-images'
        AND auth.uid() IS NOT NULL
    );
