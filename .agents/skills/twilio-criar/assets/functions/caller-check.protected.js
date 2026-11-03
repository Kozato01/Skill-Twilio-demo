// Quem está ligando, lido no Map `clientes` do Sync (serviço separado, com ACL). O Studio chama antes da
// ConversationRelay para saudar pelo nome. Protected pelo nome do arquivo: só a Twilio chama, assinado.
// Variáveis (functions/.env): SYNC_CLIENTES_SERVICE_SID, SAUDACAO_GERAL.
// Nunca falha: sem item ou com erro, devolve a saudação geral e a ligação segue. Não fale dado do cliente aqui:
// quem atende o telefone pode não ser ele.
exports.handler = async (context, event, callback) => {
  const telefone = String(event.from || event.From || '').replace(/\D/g, '');
  const desconhecido = { conhecido: false, saudacao: context.SAUDACAO_GERAL };
  if (!telefone || !context.SYNC_CLIENTES_SERVICE_SID) return callback(null, desconhecido);
  try {
    const item = await context.getTwilioClient().sync.v1
      .services(context.SYNC_CLIENTES_SERVICE_SID).syncMaps('clientes').syncMapItems(telefone).fetch();
    return callback(null, {
      conhecido: true,
      primeiro_nome: item.data.primeiro_nome,
      saudacao: `Olá, ${item.data.primeiro_nome}! Esta ligação pode ser gravada. Como posso ajudar?`,
    });
  } catch (e) {
    if (e.status !== 404) console.error('caller-check', e.message);
    return callback(null, desconhecido);
  }
};
