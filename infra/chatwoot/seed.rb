# A dedicated synthetic workspace. Idempotent; never creates or repairs automation rules.
require 'json'
require 'fileutils'

account = Account.find_or_create_by!(name: 'Northstar Goods')
email = ENV.fetch('APPDNA_ADMIN_EMAIL')
user = User.find_or_initialize_by(email: email)
if user.new_record?
  user.name = 'Northstar Demo Administrator'
  user.password = ENV.fetch('APPDNA_ADMIN_PASSWORD')
  user.skip_confirmation!
  user.save!
end
AccountUser.find_or_create_by!(account: account, user: user) { |membership| membership.role = :administrator }
%w[Billing Logistics].push('Customer Care').each do |name|
  Team.find_or_create_by!(account: account, name: name.downcase)
end
inbox = account.inboxes.find_by(name: 'AppDNA synthetic inbox')
unless inbox
  channel = Channel::Api.create!(account: account)
  inbox = Inbox.create!(account: account, channel: channel, name: 'AppDNA synthetic inbox', enable_auto_assignment: false)
end
InboxMember.find_or_create_by!(inbox: inbox, user: user)
account.custom_attribute_definitions.find_or_create_by!(attribute_key: 'customer_tier', attribute_model: :contact_attribute) do |attribute|
  attribute.attribute_display_name = 'Customer tier'
  attribute.attribute_display_type = :text
end
token = user.access_token || user.create_access_token!
FileUtils.mkdir_p('/app/appdna-output')
File.write('/app/appdna-output/connection.json', JSON.generate({account_id: account.id, inbox_id: inbox.id, api_token: token.token}))
File.chmod(0600, '/app/appdna-output/connection.json')
Redis::Alfred.delete(Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING)
puts "Prepared Northstar account #{account.id}, API inbox #{inbox.id}, three teams and the customer_tier attribute."
puts 'Connection details saved to the local ignored output directory. Existing automation rules were not modified.'
