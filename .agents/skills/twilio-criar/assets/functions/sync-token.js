// Token do Sync para o navegador assinar os sinais ("mudou, busque na API"). Visibilidade: public.
// Variáveis (functions/.env): SYNC_API_KEY_SID, SYNC_API_KEY_SECRET, SYNC_SERVICE_SID.
// ponytail: qualquer um com a URL recebe token do serviço inteiro. Nesse serviço, só sinais sem dado de cliente;
// antes de cliente real, ligue a ACL com permissão só de leitura.
exports.handler = (context, event, callback) => {
  const { AccessToken } = Twilio.jwt;
  const token = new AccessToken(context.ACCOUNT_SID, context.SYNC_API_KEY_SID, context.SYNC_API_KEY_SECRET,
    { identity: `web-${Date.now()}`, ttl: 3600 });
  token.addGrant(new AccessToken.SyncGrant({ serviceSid: context.SYNC_SERVICE_SID }));

  const res = new Twilio.Response();
  res.appendHeader('Access-Control-Allow-Origin', '*');
  res.appendHeader('Content-Type', 'application/json');
  res.setBody({ token: token.toJwt() });
  callback(null, res);
};
